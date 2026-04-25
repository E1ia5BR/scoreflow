from __future__ import annotations
from celery import Celery
import time
import os
import json
import datetime
import redis

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app = Celery('tasks', broker=broker_url)

try:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    redis_client.ping()
except:
    redis_client = None

def update_status(job_id: str, status: str, progress: float, message: str):
    if redis_client:
        payload = json.dumps({
            "id": job_id,
            "status": status,
            "progress": progress,
            "message": message
        })
        redis_client.set(f"job:{job_id}", payload)
        # Publish to WebSocket channel for real-time updates
        try:
            redis_client.publish(f"job_updates:{job_id}", payload)
        except Exception:
            pass  # pub/sub failure should not break the pipeline

import numpy as np
import soundfile as sf
import music21
import subprocess
import librosa
import noisereduce as nr

# Beat alignment: detects downbeat offset and shifts score so beat 1 → offset 0
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from beat_alignment import detect_downbeat_offset, apply_beat_alignment, fix_smart_anacrusis

# Musical intelligence: rhythmic defragmentation, figure fusion, adaptive grid
from music_intelligence import apply_musical_intelligence

# Auto-detection: BPM from audio, time signature, dynamics
from auto_detect import detect_bpm_from_audio, detect_time_signature, add_dynamics_from_velocity

# PDF export (optional — requires MuseScore or LilyPond)
from pdf_export import generate_pdf

# Cleanup utilities
from cleanup import cleanup_intermediate_files

# Ensemble transcription (runs both Magenta + Basic Pitch)
from ensemble import transcribe_ensemble

def pre_process_audio(file_path: str, audio_type: str, job_id: str) -> str:
    """
    Applies loudness normalization via ffmpeg and noise reduction via noisereduce.
    """
    audio_dir = os.path.dirname(file_path)
    audio_basename = os.path.basename(file_path)
    file_name_without_ext = os.path.splitext(audio_basename)[0]
    
    # 1. Normalize loudness to -16 LUFS (good standard for clarity)
    norm_path = os.path.join(audio_dir, file_name_without_ext + "_norm.wav")
    update_status(job_id, "preprocessing", 30, "Normalizando volume do áudio...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path, 
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            norm_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Verify the file was created and isn't empty before using it
        if os.path.exists(norm_path) and os.path.getsize(norm_path) > 0:
            current_path = norm_path
        else:
            print("Warning: ffmpeg normalization returned silently but files are broken")
            current_path = file_path
    except Exception as e:
        print(f"Warning: ffmpeg loudness normalization failed: {str(e)}")
        current_path = file_path # Fallback to original

    # 2. Apply Noise Reduction
    clean_path = os.path.join(audio_dir, file_name_without_ext + "_clean.wav")
    update_status(job_id, "preprocessing", 40, "Removendo ruído de fundo com IA...")
    try:
        # Load audio (mono) to process noise reduction using soundfile
        y, sr = sf.read(current_path)
        if len(y.shape) > 1: # Convert to mono if stereo
            y = y.mean(axis=1)
        # Perform noise reduction
        # prop_decrease=0.8 means 80% noise reduction, to avoid robotic artifacts
        reduced_noise = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.8, n_jobs=1)
        # Save clean audio
        sf.write(clean_path, reduced_noise, sr)
        
        # Free memory immediately
        del y, reduced_noise
        import gc
        gc.collect()
        
        return clean_path
    except Exception as e:
        import traceback
        print(f"Warning: noisereduce failed:\n{traceback.format_exc()}")
        return current_path # Fallback if reduction fails

def transcribe_audio_to_score(audio_path: str) -> tuple[music21.stream.Score, list]:
    """
    Transcribe piano/banda audio using the Magenta HTTP microservice (Docker port 8002).
    Calling via HTTP allows the local Windows Celery worker to use Magenta,
    which only runs inside the Linux Docker container.
    """
    import requests
    audio_path = os.path.abspath(audio_path)
    audio_dir = os.path.dirname(audio_path)
    audio_basename = os.path.basename(audio_path)
    file_name_without_ext = os.path.splitext(audio_basename)[0]

    midi_path = os.path.join(audio_dir, file_name_without_ext + "_magenta.mid")

    try:
        magenta_url = os.environ.get("MAGENTA_URL", "http://localhost:8002/transcribe")
        with open(audio_path, 'rb') as f:
            response = requests.post(magenta_url, files={"audio": f}, timeout=600)

        if response.status_code != 200:
            raise ValueError(f"Magenta HTTP Error {response.status_code}: {response.text}")

        with open(midi_path, 'wb') as f:
            f.write(response.content)

    except Exception as e:
        raise ValueError(f"Magenta API transcription failed: {str(e)}")

    if not os.path.exists(midi_path):
        raise ValueError("Magenta API output MIDI not found.")

    try:
        score = music21.converter.parse(midi_path)
    except Exception as e:
        raise ValueError(f"Failed to parse Magenta MIDI: {str(e)}")

    notes = list(score.flatten().notes)
    return score, notes


def transcribe_audio_vocal(audio_path: str) -> tuple[music21.stream.Score, list]:
    import requests
    audio_path = os.path.abspath(audio_path)
    audio_dir = os.path.dirname(audio_path)
    audio_basename = os.path.basename(audio_path)
    file_name_without_ext = os.path.splitext(audio_basename)[0]
    
    midi_path = os.path.join(audio_dir, file_name_without_ext + "_basic_pitch.mid")
    
    try:
        basic_pitch_url = os.environ.get("BASIC_PITCH_URL", "http://localhost:8001/transcribe")
        with open(audio_path, 'rb') as f:
            response = requests.post(basic_pitch_url, files={"audio": f})
        
        if response.status_code != 200:
            raise ValueError(f"HTTP Error {response.status_code}: {response.text}")
            
        with open(midi_path, 'wb') as f:
            f.write(response.content)
            
    except Exception as e:
         raise ValueError(f"Basic Pitch API transcription failed: {str(e)}")
         
    if not os.path.exists(midi_path):
         raise ValueError("Basic Pitch API output MIDI not found.")
         
    try:
        score = music21.converter.parse(midi_path)
    except Exception as e:
        raise ValueError(f"Failed to parse generated MIDI: {str(e)}")
        
    notes = list(score.flatten().notes)
    return score, notes

def clean_and_quantize_score(score: music21.stream.Score, audio_type: str = "piano") -> tuple[music21.stream.Score, float]:
    """
    Cleans raw AI-generated MIDI notes:
    1. Removes ghost notes (very short + low velocity)
    2. Uses music21's robust quantizer to snap to 16th/8th grids
    3. Formats it for readability (splitting hands for piano)
    
    IMPORTANT: Offsets must be obtained from the FLAT stream to get absolute positions.
    Using recurse() or iterating over a Part with measures returns RELATIVE offsets
    (relative to the measure), which causes all notes to pile up at measure start
    and results in only 2-3 measures being generated regardless of song length.
    """
    import copy
    
    # --- Step 1: Collect all notes with their ABSOLUTE offsets from the flat stream ---
    # score.flatten() is critical here: it collapses all hierarchical containers
    # (parts, measures, voices) and returns elements with their absolute offsets.
    flat_score = score.flatten()
    
    # Preserve tempo from original MIDI so beat durations are correct
    tempo_marks = list(flat_score.getElementsByClass(music21.tempo.MetronomeMark))
    
    # Extract first detected tempo in BPM (to pass back for beat alignment)
    detected_bpm = 0.0
    if tempo_marks:
        try:
            detected_bpm = float(tempo_marks[0].number)
        except Exception:
            pass
    
    valid_notes = []  # list of (absolute_offset, note_deepcopy)
    for el in flat_score.getElementsByClass(['Note', 'Chord']):
        n = copy.deepcopy(el)
        # --- Ghost note removal ---
        if n.quarterLength < 0.125:
            if hasattr(n, 'volume') and n.volume.velocity is not None and n.volume.velocity < 50:
                continue  # Low-velocity noise
            elif n.quarterLength < 0.05:
                continue  # Way too short even if loud
        # el.offset is the ABSOLUTE offset because we got el from the flat stream
        valid_notes.append((el.offset, n))

    # --- Step 2: Build a flat temp part and quantize ---
    temp_part = music21.stream.Part()
    
    # Restore tempo marks so quantization is meaningful
    for tm in tempo_marks:
        temp_part.insert(tm.offset, copy.deepcopy(tm))
    
    for abs_offset, n in valid_notes:
        temp_part.insert(abs_offset, n)

    try:
        temp_part.quantize((4, 8, 16), processOffsets=True, processDurations=True, inPlace=True)
    except Exception as e:
        print(f"Warning: music21 builtin quantize failed ({e})")

    # --- Step 3: Key analysis ---
    try:
        key = temp_part.analyze('key')
        temp_part.insert(0, key)
    except Exception as e:
        print(f"Warning: Harmonic analysis failed ({e})")

    # --- Step 4: Split hands or build single part ---
    # Again, use temp_part.flat to get absolute offsets after quantization
    new_score = music21.stream.Score()
    
    # Restore tempo marks to the new score
    for tm in tempo_marks:
        new_score.insert(tm.offset, copy.deepcopy(tm))

    if audio_type == "piano" or audio_type == "banda":
        treble_part = music21.stream.Part()
        bass_part = music21.stream.Part()
        treble_part.insert(0, music21.clef.TrebleClef())
        bass_part.insert(0, music21.clef.BassClef())

        # Iterate the FLAT temp_part to get absolute offsets
        for el in temp_part.flat.getElementsByClass(['Note', 'Chord']):
            n = copy.deepcopy(el)
            abs_off = el.offset  # absolute because we're using .flat
            if el.isChord:
                avg_midi = sum([p.midi for p in el.pitches]) / len(el.pitches)
                if avg_midi >= 60:
                    treble_part.insert(abs_off, n)
                else:
                    bass_part.insert(abs_off, n)
            else:
                if el.pitch.midi >= 60:
                    treble_part.insert(abs_off, n)
                else:
                    bass_part.insert(abs_off, n)

        treble_part = treble_part.chordify()
        bass_part = bass_part.chordify()
        new_score.insert(0, treble_part)
        new_score.insert(0, bass_part)
    else:
        part = music21.stream.Part()
        for el in temp_part.flat.getElementsByClass(['Note', 'Chord']):
            part.insert(el.offset, copy.deepcopy(el))
        new_score.insert(0, part.chordify())

    return new_score, detected_bpm

@celery_app.task(name='tasks.process_audio')
def process_audio(job_id: str, file_path: str, time_signature_str: str = "4/4", audio_type: str = "piano"):
    update_status(job_id, "analyzing", 20, "Checking format and duration...")
    time.sleep(1)
    
    # Pre-processing step: Normalize and Reduce noise
    cleaned_file_path = pre_process_audio(file_path, audio_type, job_id)
    
    # --- Phase 1: Auto-detect BPM from audio ---
    update_status(job_id, "analyzing", 42, "Detectando BPM do áudio... / Detecting BPM...")
    audio_bpm, bpm_confidence = detect_bpm_from_audio(cleaned_file_path)
    print(f"DEBUG: Audio BPM = {audio_bpm:.1f} (confidence: {bpm_confidence:.2f})", flush=True)
    
    # --- Phase 1: Auto-detect time signature if requested ---
    if time_signature_str == "auto":
        update_status(job_id, "analyzing", 45, "Detectando compasso... / Detecting time signature...")
        time_signature_str, ts_confidence = detect_time_signature(cleaned_file_path, audio_bpm)
        print(f"DEBUG: Auto-detected time signature = {time_signature_str} (confidence: {ts_confidence:.2f})", flush=True)
    
    update_status(job_id, "transcribing", 50, "Processing audio locally...")
    try:
        if audio_type == "vocal":
            score, notes = transcribe_audio_vocal(cleaned_file_path)
        else:
            # Try ensemble (both models) first, fall back to single model
            try:
                score, notes = transcribe_ensemble(cleaned_file_path)
                print("DEBUG: Ensemble transcription succeeded", flush=True)
            except Exception as _ens_err:
                print(f"DEBUG: Ensemble failed ({_ens_err}), using Magenta only", flush=True)
                score, notes = transcribe_audio_to_score(cleaned_file_path)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        update_status(job_id, "error", 100, f"Error transcribing audio: {str(e)}\n\n{err_msg}")
        return "ERROR"
    
    update_status(job_id, "converting", 85, "Music21 converting MIDI to XML...")
    
    # Validation step
    if len(score.flatten().notes) < 3:
        update_status(job_id, "error", 100, "Transcription failed: too few notes detected (< 3).")
        return "ERROR"
        
    # Apply Time Signature and Clean up rhythms generated by raw AI timings
    print(f"DEBUG TIME SIGNATURE: {time_signature_str}", flush=True)
    
    # Save a fallback copy in case music21 fails to format the complex rhythms
    import copy
    score_fallback = copy.deepcopy(score)
    
    # Log total duration before processing so we can verify measure count
    try:
        total_duration_ql = score.flatten().highestTime
        print(f"DEBUG: Total score duration = {total_duration_ql:.2f} quarter-lengths before cleanup", flush=True)
    except Exception:
        pass

    update_status(job_id, "converting", 90, f"Formatting score for {time_signature_str} time...")
    
    formatting_success = False
    try:
        # Remove any existing Time Signatures inherited from the MIDI's default
        for el in list(score.recurse().getElementsByClass('TimeSignature')):
            el.activeSite.remove(el)

        # 1. Clean noise, snap to grid, split hands
        score, midi_bpm = clean_and_quantize_score(score, audio_type)

        total_duration_after = score.flatten().highestTime
        print(f"DEBUG: Total score duration = {total_duration_after:.2f} quarter-lengths after cleanup", flush=True)
        print(f"DEBUG: MIDI tempo = {midi_bpm:.1f} BPM, Audio tempo = {audio_bpm:.1f} BPM", flush=True)

        # Use audio-detected BPM (more reliable than MIDI metadata)
        # Fall back to MIDI BPM only if audio detection had very low confidence
        if bpm_confidence >= 0.15 and audio_bpm > 0:
            effective_bpm = audio_bpm
            print(f"DEBUG: Using AUDIO BPM = {effective_bpm:.1f}", flush=True)
        elif midi_bpm > 0:
            effective_bpm = midi_bpm
            print(f"DEBUG: Using MIDI BPM = {effective_bpm:.1f} (audio confidence too low)", flush=True)
        else:
            effective_bpm = 120.0
            print(f"DEBUG: Using fallback BPM = 120.0", flush=True)

        # 2. Add dynamics markings from velocity data
        try:
            add_dynamics_from_velocity(score)
        except Exception as _dyn_err:
            print(f"Warning: dynamics insertion failed, skipping: {_dyn_err}", flush=True)

        try:
            score = apply_musical_intelligence(score, effective_bpm, time_signature_str)
        except Exception as _mi_err:
            import traceback
            print(f"Warning: musical intelligence failed, skipping: {_mi_err}\n{traceback.format_exc()}", flush=True)

        try:
            pickup_ql = detect_downbeat_offset(cleaned_file_path, effective_bpm, time_signature_str)
            if pickup_ql > 0.0:
                print(f"DEBUG: Applying beat alignment — pickup={pickup_ql:.2f} QL", flush=True)
                score = apply_beat_alignment(score, pickup_ql, time_signature_str)
            else:
                print("DEBUG: No pickup detected — score starts on downbeat.", flush=True)
        except Exception as _be:
            print(f"Warning: beat alignment failed, skipping: {_be}", flush=True)

        for p in score.parts:
            ts = music21.meter.TimeSignature(time_signature_str)
            for existing_ts in list(p.flat.getElementsByClass('TimeSignature')):
                existing_ts.activeSite.remove(existing_ts)
            p.insert(0, ts)

        score.makeMeasures(inPlace=True)
        
        try:
            if 'pickup_ql' in locals() and pickup_ql > 0.0:
                score = fix_smart_anacrusis(score, pickup_ql, time_signature_str)
        except Exception as _an_err:
            import traceback
            print(f"Warning: smart anacrusis fix failed: {_an_err}\n{traceback.format_exc()}", flush=True)

        score.makeNotation(inPlace=True)
        formatting_success = True

        first_part = next(iter(score.parts), None)
        if first_part:
            n_measures = len(first_part.getElementsByClass('Measure'))
            print(f"DEBUG: Score has {n_measures} measures after makeMeasures", flush=True)
    except Exception as e:
        import traceback
        err_str = traceback.format_exc()
        print(f"Warning: Score formatting failed: {str(e)}\n{err_str}")
        print("Falling back to raw AI score to ensure export succeeds.", flush=True)
        score = score_fallback
        # Update user with a warning, but task will succeed
        update_status(job_id, "converting", 95, "Aviso: ritmos complexos impediram formatação perfeita.")
    
    # Create result folder
    result_dir = os.path.join("storage", "results", job_id)
    os.makedirs(result_dir, exist_ok=True)
    
    # Cleanup memory aggressively before writing XML
    import gc
    try:
        del notes
    except NameError:
        pass
    gc.collect()
    
    # Export valid files
    xml_path = os.path.join(result_dir, "output.musicxml")
    midi_path = os.path.join(result_dir, "output.mid")
    
    try:
        score.write('musicxml', fp=xml_path)
        score.write('midi', fp=midi_path)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        # Se falhar escrever o arquivo final (ex: score muito corrompido), usa fallback como ultimo recurso
        if formatting_success:
            try:
                print(f"Score write failed, trying fallback: {str(e)}", flush=True)
                score_fallback.write('musicxml', fp=xml_path)
                score_fallback.write('midi', fp=midi_path)
                score = score_fallback
            except Exception as e_fallback:
                update_status(job_id, "error", 100, f"Erro fatal ao gerar partitura: {str(e_fallback)}")
                return "ERROR"
        else:
            update_status(job_id, "error", 100, f"Erro fatal ao gerar partitura: {str(e)}\n\n{err_msg}")
            return "ERROR"
    
    # Reload notes for logging
    try:
        notes = list(score.flatten().notes)
    except:
        notes = []
    
    with open(os.path.join(result_dir, "process.log"), "w") as f:
        f.write("Task started.\nAnalyzing...\nTranscribing...\nConverting...\nSuccess.\n")
        f.write(f"Detected {len(notes)} notes.\n")
    
    # Try to generate PDF (optional — graceful if tools not available)
    pdf_path = os.path.join(result_dir, "output.pdf")
    try:
        pdf_ok = generate_pdf(xml_path, pdf_path)
        if pdf_ok:
            print(f"DEBUG: PDF generated at {pdf_path}", flush=True)
    except Exception as _pdf_err:
        print(f"Warning: PDF generation failed: {_pdf_err}", flush=True)
        
    # Handle history tracking mapping
    history_file = "storage/history.json"
    history = []
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            try: history = json.load(f)
            except: pass
    history.insert(0, {
        "id": job_id, "name": f"Audio-{job_id[:4]}", 
        "date": datetime.datetime.now().strftime("%d/%m/%Y"), "status": "ready"
    })
    with open(history_file, "w") as f:
        json.dump(history[:10], f)
        
    update_status(job_id, "ready", 100, "Done!")

    # --- Phase 3: Cleanup intermediate files and free memory ---
    try:
        upload_dir = os.path.dirname(file_path)
        cleanup_intermediate_files(upload_dir)
    except Exception as _clean_err:
        print(f"Warning: intermediate cleanup failed: {_clean_err}", flush=True)

    # Aggressive memory cleanup after entire pipeline
    try:
        del score
    except NameError:
        pass
    try:
        del score_fallback
    except NameError:
        pass
    try:
        del notes
    except NameError:
        pass
    gc.collect()

    return "SUCCESS"

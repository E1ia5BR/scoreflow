"""
beat_alignment.py
=================
Detects the musical downbeat offset in an audio file and aligns a music21
score so that beat 1 always lands exactly at offset 0.0.

Why this matters
----------------
AI transcription models (Magenta, Basic Pitch) output MIDI where note
offset 0.0 corresponds to the first audio frame, NOT the first musical
downbeat. If a piece begins with an anacruza (pickup), every subsequent
barline will be misaligned by the length of that pickup, producing a
score that sounds right but looks rhythmically fragmented on paper.

This module:
    1. Analyses the audio with librosa to find the beat phase and locate
       where beat 1 (the first downbeat) occurs in seconds.
    2. Converts that time to quarter-lengths using the tempo embedded in
       the MIDI / score.
    3. Shifts every element in the score so the first downbeat is at 0.0
       and any preceding pickup notes sit at negative offsets — which
       music21's makeMeasures() handles cleanly as an anacruza measure.
"""

from __future__ import annotations

import math
import warnings
import traceback
import numpy as np

import librosa
import music21


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_downbeat_offset(
    audio_path: str,
    tempo_bpm: float,
    time_sig_str: str = "4/4",
) -> float:
    """
    Estimate how many quarter-lengths precede the first downbeat.

    Parameters
    ----------
    audio_path   : Path to the processed/clean audio file (WAV recommended).
    tempo_bpm    : Tempo in BPM.  Pass 0 or None to let librosa estimate it.
    time_sig_str : Time signature string such as "4/4", "3/4", "6/8".

    Returns
    -------
    pickup_ql : float
        Number of quarter-lengths that occur BEFORE the first downbeat.
        0.0 means the music starts on beat 1 (no anacruza).
        A value of e.g. 1.0 in 4/4 means a one-beat pickup (3rd beat start).
    """
    try:
        # -- Parse numerator so we know how many beats per bar -----------
        try:
            numerator = int(time_sig_str.split("/")[0])
        except Exception:
            numerator = 4

        # -- Load audio (mono, 22 kHz is plenty for beat tracking) -------
        # Use soundfile to avoid the soxr DLL bug on Windows.
        # librosa.load() would attempt to use soxr for resampling which
        # fails with a DLL error on Windows; we resample manually via scipy.
        TARGET_SR = 22050
        try:
            import soundfile as _sf
            from scipy.signal import resample_poly
            from math import gcd as _gcd

            y_raw, orig_sr = _sf.read(audio_path, dtype="float32", always_2d=False)
            # Downmix to mono
            if y_raw.ndim > 1:
                y_raw = y_raw.mean(axis=1)
            # Resample to 22050 Hz if needed
            if orig_sr != TARGET_SR:
                common = _gcd(orig_sr, TARGET_SR)
                y = resample_poly(y_raw, TARGET_SR // common, orig_sr // common)
                y = y.astype("float32")
            else:
                y = y_raw
            sr = TARGET_SR
        except Exception as _load_err:
            print(f"beat_alignment: soundfile load failed ({_load_err}), falling back to librosa.load")
            y, sr = librosa.load(audio_path, sr=TARGET_SR, mono=True)

        # -- Beat tracking (numba-free) ----------------------------------
        # librosa.beat imports numba which has broken DLLs on Python 3.14.
        # We implement tempo + beat estimation with scipy only:
        #   1. Compute onset-strength envelope (no numba needed).
        #   2. Autocorrelate to find dominant period → BPM estimate.
        #   3. Use scipy.signal.find_peaks to locate individual beat frames.
        from scipy.signal import find_peaks

        # -- Onset strength envelope (pure numpy/scipy — no librosa/numba) --
        # librosa.onset imports librosa.filters which imports numba (broken on
        # Python 3.14 Windows). We compute onset strength as spectral flux:
        # sum of positive first-differences of STFT magnitude across frames.
        from scipy.signal import stft as _stft, find_peaks

        HOP = 512  # hop frames ≈ 23ms @ 22050 Hz
        N_FFT = 2048
        _, _, Zxx = _stft(y, fs=sr, nperseg=N_FFT, noverlap=N_FFT - HOP)
        mag = np.abs(Zxx)  # shape: (freq_bins, time_frames)
        # Spectral flux: half-wave-rectified sum of positive magnitude diffs
        flux = np.sum(np.maximum(0, np.diff(mag, axis=1)), axis=0)
        onset_env = flux  # shape: (time_frames - 1,)

        # Estimate tempo from autocorrelation if not supplied
        if not (tempo_bpm and tempo_bpm > 0):
            ac = np.correlate(onset_env, onset_env, mode='full')
            ac = ac[len(ac) // 2:]  # keep positive lags only
            # BPM 40..240 → period seconds 60/240..60/40 → lag frames
            lag_min = max(1, int(60 / 240 * sr / HOP))
            lag_max = min(int(60 / 40 * sr / HOP), len(ac) - 1)
            if lag_max > lag_min:
                best_lag = int(np.argmax(ac[lag_min:lag_max])) + lag_min
                tempo_bpm = 60.0 / (best_lag * HOP / sr)
            else:
                tempo_bpm = 120.0  # safe fallback

        # Locate beats: peaks in onset envelope spaced ~one beat period apart
        beat_period_frames = max(1, int(round(60.0 / tempo_bpm * sr / HOP)))
        min_dist = max(1, int(beat_period_frames * 0.6))
        beat_frames_arr, _ = find_peaks(onset_env, distance=min_dist)

        if len(beat_frames_arr) == 0:
            print("beat_alignment: no beats detected — returning 0 pickup.")
            return 0.0

        # Convert beat frame indices → time in seconds
        beat_times = beat_frames_arr * HOP / sr

        # onset strength at each beat (for downbeat phase detection)
        onset_at_beats = onset_env[beat_frames_arr]

        downbeat_idx = _find_downbeat_index(onset_at_beats, numerator)
        downbeat_time_sec = beat_times[downbeat_idx]

        # -- Convert seconds → quarter-lengths ---------------------------
        # At tempo_bpm BPM, one quarter-note = 60 / tempo_bpm seconds
        seconds_per_ql = 60.0 / tempo_bpm
        pickup_ql = downbeat_time_sec / seconds_per_ql

        # Snap to nearest 16th note (0.25 QL) to avoid floating-point drift
        pickup_ql = round(pickup_ql * 4) / 4

        # Clamp: pickup can't be >= one full bar
        beats_per_bar_ql = _beats_per_bar_in_ql(time_sig_str)
        if pickup_ql >= beats_per_bar_ql:
            pickup_ql = 0.0

        print(
            f"beat_alignment: tempo={tempo_bpm:.1f} BPM, "
            f"downbeat at {downbeat_time_sec:.3f}s, "
            f"pickup={pickup_ql:.2f} QL"
        )
        return pickup_ql

    except Exception:
        print(f"beat_alignment: detection failed, using 0 pickup:\n{traceback.format_exc()}")
        return 0.0


def apply_beat_alignment(
    score: music21.stream.Score,
    pickup_ql: float,
    time_sig_str: str = "4/4",
) -> music21.stream.Score:
    """
    Shift every element in *score* so that the first downbeat falls at an
    offset that equals the length of one full bar.

    music21's makeMeasures() cannot cope with negative offsets, so instead
    of shifting pickup notes to negative positions we shift the entire score
    *forward* by (bar_ql - pickup_ql).  The result:

        • Pickup notes start at offset (bar_ql - pickup_ql)
        • The first downbeat (beat 1, measure 2) starts at offset bar_ql
        • makeMeasures() sees the first bar as mostly-rest + pickup notes
          and renders it as the correct anacruza measure.

    Example — 4/4, pickup = 1 beat (1.0 QL), bar = 4 beats (4.0 QL):
        shift_amount = 4.0 - 1.0 = 3.0 QL
        pickup note   → offset 3.0  (beat 4 of the first dummy bar)
        downbeat note → offset 4.0  (beat 1 of the real first full bar)

    Parameters
    ----------
    score        : A music21 Score (flat parts, post-quantization).
    pickup_ql    : Quarter-lengths of anacruza (from detect_downbeat_offset).
    time_sig_str : Time signature string, needed to know bar length.

    Returns
    -------
    The modified Score (new object with shifted offsets).
    """
    if pickup_ql <= 0.0:
        return score  # Nothing to do

    try:
        bar_ql = _beats_per_bar_in_ql(time_sig_str)
        shift_amount = bar_ql - pickup_ql  # always >= 0 (we clamped pickup earlier)
        if shift_amount <= 0.0:
            return score

        import copy

        new_score = music21.stream.Score()

        # Carry over top-level non-part elements (tempo, metadata …)
        for el in score.getElementsByClass(
            ['MetronomeMark', 'MetadataBundle', 'Metadata']
        ):
            new_score.insert(el.offset, copy.deepcopy(el))

        for part in score.parts:
            new_part = music21.stream.Part()

            # Copy clef / key / time sig at offset 0 if present
            for el in part.flat.getElementsByClass(
                ['Clef', 'KeySignature', 'TimeSignature', 'MetronomeMark']
            ):
                new_part.insert(0, copy.deepcopy(el))

            # Shift every note/chord forward by shift_amount
            for el in part.flat.getElementsByClass(['Note', 'Chord']):
                new_el = copy.deepcopy(el)
                new_part.insert(el.offset + shift_amount, new_el)

            new_score.append(new_part)

        first_offset = _first_note_offset(new_score)
        print(
            f"beat_alignment: shifted score by +{shift_amount:.2f} QL "
            f"(bar={bar_ql:.1f} QL, pickup={pickup_ql:.2f} QL). "
            f"First note now at offset {first_offset:.2f} QL."
        )
        return new_score

    except Exception:
        print(f"beat_alignment: shift failed, returning original:\n{traceback.format_exc()}")
        return score

def fix_smart_anacrusis(
    score: music21.stream.Score,
    pickup_ql: float,
    time_sig_str: str = "4/4",
) -> music21.stream.Score:
    """
    Remove pausas de preenchimento (rests) introduzidas no primeiro compasso se ele
    for uma anacruse. Recalcula os offsets para que a exportação MusicXML seja perfeita.
    
    Deve ser chamada APÓS score.makeMeasures() para limpar o primeiro compasso gerado.
    """
    if pickup_ql <= 0.0:
        return score
        
    try:
        bar_ql = _beats_per_bar_in_ql(time_sig_str)
        shift_amount = bar_ql - pickup_ql
        if shift_amount <= 0.0:
            return score
            
        for p in score.parts:
            measures = p.getElementsByClass('Measure')
            if not measures:
                continue
                
            first_measure = measures[0]
            
            # Remove as pausas que antecedem a nota na anacruse 
            rests = list(first_measure.getElementsByClass('Rest'))
            for r in rests:
                first_measure.remove(r)
                
            # Desloca as notas para começarem do offset 0 interno ao compasso
            elements_to_shift = list(first_measure.elements)
            for el in elements_to_shift:
                # Não desloca itens que definem a estrutura (Clave, Armadura, Compasso, Metrônomo)
                # O offset deles será 0 já.
                if isinstance(el, (music21.clef.Clef, music21.meter.TimeSignature, music21.key.KeySignature, music21.tempo.MetronomeMark)):
                    continue
                first_measure.remove(el)
                first_measure.insert(el.offset - shift_amount, el)
                
            first_measure.number = 0
            first_measure.padAsAnacrusis()
            
        print(f"beat_alignment: smart anacrusis aplicada. Removidas pausas e notas alinhadas.", flush=True)
        return score
    except Exception:
        print(f"beat_alignment: smart anacrusis falhou:\n{traceback.format_exc()}")
        return score




# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_downbeat_index(onset_at_beats: np.ndarray, numerator: int) -> int:
    """
    Find the index of the first *likely* downbeat within the beat array.

    Strategy:
    - Try every `numerator`-th position (0, numerator, 2*numerator, …).
    - Among those candidates, pick the one with the highest onset strength.
    - If the raw first beat (index 0) is within 1 position of best, use 0.
    - Fall back to 0 if inconclusive.
    """
    n = len(onset_at_beats)
    if n == 0:
        return 0

    if numerator <= 1 or n < numerator:
        return 0  # Can't determine phase with so few beats

    # Try each possible phase offset (0..numerator-1)
    best_phase = 0
    best_score = -1.0
    for phase in range(min(numerator, n)):
        candidates = onset_at_beats[phase::numerator]
        mean_strength = float(np.mean(candidates))
        if mean_strength > best_score:
            best_score = mean_strength
            best_phase = phase

    return best_phase


def _beats_per_bar_in_ql(time_sig_str: str) -> float:
    """Return the length of one bar in quarter-lengths for a given time signature."""
    try:
        ts = music21.meter.TimeSignature(time_sig_str)
        return ts.barDuration.quarterLength
    except Exception:
        return 4.0


def _first_note_offset(score: music21.stream.Score) -> float:
    """Return the offset of the first note in the flat score."""
    try:
        notes = list(score.flatten().getElementsByClass(['Note', 'Chord']))
        if notes:
            return notes[0].offset
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== beat_alignment self-test ===")

    # Build a synthetic score with a 1-beat anacruza in 4/4
    test_score = music21.stream.Score()
    part = music21.stream.Part()
    part.insert(0, music21.clef.TrebleClef())

    # Pickup note at QL 0 → should end up at -1.0 after a 1-beat shift
    pickup_note = music21.note.Note("E4")
    pickup_note.quarterLength = 1.0
    part.insert(0, pickup_note)

    # Downbeat note at QL 1 → should end up at 0.0
    note1 = music21.note.Note("C4")
    note1.quarterLength = 1.0
    part.insert(1.0, note1)

    note2 = music21.note.Note("D4")
    note2.quarterLength = 1.0
    part.insert(2.0, note2)

    test_score.append(part)

    print("Before alignment:")
    for n in test_score.flatten().getElementsByClass(['Note']):
        print(f"  {n.nameWithOctave} @ offset {n.offset}")

    aligned = apply_beat_alignment(test_score, pickup_ql=1.0)

    print("After alignment (pickup_ql=1.0):")
    for n in aligned.flatten().getElementsByClass(['Note']):
        print(f"  {n.nameWithOctave} @ offset {n.offset}")

    # Make measures
    for p in aligned.parts:
        ts = music21.meter.TimeSignature("4/4")
        p.insert(0, ts)
    aligned.makeMeasures(inPlace=True)
    aligned.makeNotation(inPlace=True)
    aligned.write("musicxml", "test_beat_aligned_self.musicxml")
    print("Written: test_beat_aligned_self.musicxml")

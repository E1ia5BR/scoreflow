import os
import shutil
import tempfile
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

MODEL_DIR = "/opt/model/train"
if not os.path.exists(MODEL_DIR):
    MODEL_DIR = "/opt/model"

@app.get("/health")
def health():
    return {"status": "ok", "model_dir": MODEL_DIR, "model_exists": os.path.exists(MODEL_DIR)}

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Receives an audio file, runs Magenta Onsets & Frames transcription on it,
    and returns the resulting MIDI file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save uploaded audio to temp dir
        audio_path = os.path.join(tmpdir, audio.filename)
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Convert to WAV using soundfile (Magenta requires uncompressed WAV)
        import soundfile as sf
        base_name = os.path.splitext(audio.filename)[0]
        wav_path = os.path.join(tmpdir, base_name + "_converted.wav")
        try:
            data, samplerate = sf.read(audio_path)
            sf.write(wav_path, data, samplerate)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to convert audio to WAV: {str(e)}")

        # Run Magenta CLI
        cmd = [
            "onsets_frames_transcription_transcribe",
            "--model_dir", MODEL_DIR,
            wav_path
        ]
        result = subprocess.run(cmd, capture_output=True, cwd=tmpdir)

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Magenta failed:\n{result.stderr.decode()}\n{result.stdout.decode()}"
            )

        # Magenta appends .midi to the wav filename: e.g. "audio_converted.wav.midi"
        wav_basename = os.path.basename(wav_path)
        midi_path = os.path.join(tmpdir, wav_basename + ".midi")
        if not os.path.exists(midi_path):
            midi_path = os.path.join(tmpdir, wav_basename + ".mid")
            if not os.path.exists(midi_path):
                raise HTTPException(
                    status_code=500,
                    detail=f"Magenta MIDI output not found. Logs:\n{result.stderr.decode()}"
                )

        # Copy out of tmpdir before it's destroyed
        out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mid")
        shutil.copy2(midi_path, out_temp.name)
        out_temp.close()

        return FileResponse(out_temp.name, media_type="audio/midi", filename="output.mid")

import numpy as np
import librosa
import soundfile as sf
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from worker.tasks import transcribe_audio_to_score

def generate_tone(freq, sr, duration):
    t = np.linspace(0, duration, int(sr * duration), False)
    return np.sin(freq * t * 2 * np.pi)

def create_test_wav(filepath):
    sr = 22050
    # Generate 3 distinct tones: C4 (261.63), D4 (293.66), E4 (329.63)
    tone1 = generate_tone(261.63, sr, 1.0)
    tone2 = generate_tone(293.66, sr, 1.0)
    tone3 = generate_tone(329.63, sr, 1.0)
    silence = np.zeros(sr//2)
    
    audio = np.concatenate([tone1, silence, tone2, silence, tone3])
    sf.write(filepath, audio, sr)

def test_transcription():
    print("Generating test_gen.wav...")
    wav_path = "test_gen.wav"
    create_test_wav(wav_path)
    
    print("Running transcribe_audio_to_score...")
    try:
        score, notes = transcribe_audio_to_score(wav_path)
        
        print(f"Detected {len(notes)} notes.")
        assert len(notes) >= 3, f"Expected at least 3 notes, got {len(notes)}"
        
        # check that we can export to musicxml
        score.write('musicxml', fp='test_out.musicxml')
        print("Exported to test_out.musicxml successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED WITH Exception: {e}")
    
    if os.path.exists(wav_path):
        os.remove(wav_path)
    if os.path.exists('test_out.musicxml'):
        os.remove('test_out.musicxml')
        
    print("Test finished!")

if __name__ == "__main__":
    test_transcription()

import sys
import os
import music21

# Ensure the correct path is used
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    job_id = "545659f4-9b0c-4af6-9e51-f7be30836284"
    audio_path = f"storage/uploads/{job_id}/test_converted.wav.midi"
    
    print(f"Parsing {audio_path}...")
    score = music21.converter.parse(audio_path)
    notes = list(score.flatten().notes)
    
    print(f"Total Notes: {len(notes)}")
    print(f"Total Elements: {len(score.flatten())}")
    
    print("Writing to XML...")
    score.write("musicxml", "test_simplify.xml")
    print("Done")

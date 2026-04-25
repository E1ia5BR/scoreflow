import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worker.tasks import transcribe_audio_to_score

if __name__ == "__main__":
    job_id = "545659f4-9b0c-4af6-9e51-f7be30836284"
    audio_path = f"storage/uploads/{job_id}/test.mp3"
    
    try:
        print(f"Running transcribe_audio_to_score for {audio_path}...")
        score, notes = transcribe_audio_to_score(audio_path)
        
        print("Writing musicxml")
        xml_path = os.path.join(os.path.dirname(audio_path), "test.musicxml")
        score.write('musicxml', fp=xml_path)
    except Exception as e:
        import traceback
        with open("error.log", "w") as f:
            f.write(traceback.format_exc())
            f.write(f"\n{str(e)}")
        print("Wrote error to error.log")
        exit(1)

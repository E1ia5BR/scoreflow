import os
import music21
import copy
from worker.tasks import clean_and_quantize_score
from music_intelligence import apply_musical_intelligence
from beat_alignment import apply_beat_alignment, fix_smart_anacrusis

def run_test():
    midi_path = r"storage/uploads/3cbfa882-e233-4c40-bc36-9b61e5ceb48c/piano audio flow_clean_magenta.mid"
    score = music21.converter.parse(midi_path)
    time_signature_str = "3/8"
    
    s1, bpm = clean_and_quantize_score(score, "piano")
    s2 = apply_musical_intelligence(s1, bpm, time_signature_str)
    
    pickup_ql = 1.0
    if pickup_ql > 0.0:
        s2 = apply_beat_alignment(s2, pickup_ql, time_signature_str)
    
    ts = music21.meter.TimeSignature(time_signature_str)
    for p in s2.parts:
        for existing_ts in list(p.flat.getElementsByClass('TimeSignature')):
            existing_ts.activeSite.remove(existing_ts)
        p.insert(0, ts)
        
    s2.makeMeasures(inPlace=True)
    if pickup_ql > 0.0:
        s2 = fix_smart_anacrusis(s2, pickup_ql, time_signature_str)
    s2.makeNotation(inPlace=True)
    
    print("Exporting to MusicXML...")
    try:
        s2.write('musicxml', fp='test_out.musicxml')
        print("Success XML!")
    except Exception as e:
        print(f"FAILED XML: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()

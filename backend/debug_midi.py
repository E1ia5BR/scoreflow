import traceback
import music21

try:
    print("Parsing MIDI...")
    score = music21.converter.parse('/app/test_gen.wav.midi')
    print("Successfully parsed. Notes:")
    print(len(score.flatten().notes))
except Exception as e:
    print("Failed to parse MIDI:")
    traceback.print_exc()

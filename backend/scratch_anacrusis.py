import music21

score = music21.stream.Score()
part = music21.stream.Part()

pickup_note = music21.note.Note('C4')
pickup_note.quarterLength = 1.0

downbeat_note = music21.note.Note('D4')
downbeat_note.quarterLength = 4.0

# Current beat_alignment logic: shift forward so downbeat lands on bar_ql (4.0)
pickup_ql = 1.0
bar_ql = 4.0
shift = bar_ql - pickup_ql # 3.0

part.insert(shift, pickup_note)
part.insert(bar_ql, downbeat_note)

ts = music21.meter.TimeSignature('4/4')
part.insert(0.0, ts)
score.insert(0.0, part)

score.makeMeasures(inPlace=True)
score.makeNotation(inPlace=True)

for p in score.parts:
    first_measure = p.getElementsByClass('Measure')[0]
    print(f"Measure 0 length before: {first_measure.highestTime}")
    for el in first_measure:
        print(f"  {el} at offset {el.offset}")
        
    # Apply smart anacrusis fix:
    shift_amount = bar_ql - pickup_ql
    
    # 1. Remove rests
    rests = list(first_measure.getElementsByClass('Rest'))
    for r in rests:
        first_measure.remove(r)
        
    # 2. Shift remaining elements backwards
    elements_to_shift = list(first_measure.elements)
    for el in elements_to_shift:
        # Don't shift Clef, TimeSignature, KeySignature
        if isinstance(el, (music21.clef.Clef, music21.meter.TimeSignature, music21.key.KeySignature)):
            continue
        # Shift notes
        first_measure.remove(el)
        first_measure.insert(el.offset - shift_amount, el)
        
    # Mark as pickup
    first_measure.number = 0
    first_measure.padAsAnacrusis() # This adjusts paddingLeft internally

    print(f"Measure 0 length after: {first_measure.highestTime}")
    for el in first_measure:
        print(f"  {el} at offset {el.offset}")

score.write('musicxml', 'C:/Users/elias/Documents/transcribe-ai 2.0/backend/test_anacrusis_out.musicxml')
print("Written")

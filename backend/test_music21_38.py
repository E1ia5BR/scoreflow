import music21

score = music21.stream.Score()
part = music21.stream.Part()

# Add a note that crosses many barlines in 3/8
long_note = music21.note.Note('C4')
long_note.quarterLength = 10.0 # very long note
part.insert(0, long_note)

score.insert(0, part)
ts = music21.meter.TimeSignature('3/8')
part.insert(0, ts)

print("Running makeMeasures...")
score.makeMeasures(inPlace=True)
print("Done!")

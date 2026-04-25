import music21
import copy

s = music21.stream.Score()
p = music21.stream.Part()
m = music21.stream.Measure()
n = music21.note.Note("C4")
n.quarterLength = 1.0

m.insert(2.0, n)
p.insert(4.0, m)
s.insert(0.0, p)

flat = s.flatten()
n_flat = list(flat.notes)[0]

n_copy = copy.deepcopy(n_flat)
n_copy.offset = n_flat.offset

print(f"n_copy fixed offset: {n_copy.offset}")

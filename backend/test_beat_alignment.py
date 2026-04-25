"""
test_beat_alignment.py
======================
End-to-end test for the beat_alignment module.
Runs two tests:
  1. Self-test: synthetic score with known anacruza
  2. Real-audio test: loads test_real.wav and calls detect_downbeat_offset
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import music21
from beat_alignment import detect_downbeat_offset, apply_beat_alignment

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 – Synthetic score with a 1-beat anacruza
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Synthetic score — apply_beat_alignment(pickup_ql=1.0)")
print("=" * 60)

test_score = music21.stream.Score()
part = music21.stream.Part()
part.insert(0, music21.clef.TrebleClef())

# Pickup note at QL 0 → should become offset -1.0 after shift
pickup = music21.note.Note("E4")
pickup.quarterLength = 1.0
part.insert(0.0, pickup)

# Beat-1 note at QL 1 → should become offset 0.0
n1 = music21.note.Note("C4")
n1.quarterLength = 1.0
part.insert(1.0, n1)

n2 = music21.note.Note("D4")
n2.quarterLength = 1.0
part.insert(2.0, n2)

n3 = music21.note.Note("E4")
n3.quarterLength = 1.0
part.insert(3.0, n3)

n4 = music21.note.Note("F4")
n4.quarterLength = 1.0
part.insert(4.0, n4)

test_score.append(part)

print("\nBefore alignment:")
for n in test_score.flatten().getElementsByClass(['Note']):
    print(f"  {n.nameWithOctave} @ offset {n.offset:.2f}")

aligned = apply_beat_alignment(test_score, pickup_ql=1.0, time_sig_str="4/4")

# Forward shift by (4.0 - 1.0) = 3.0 QL
# Expected: E4→3.0, C4→4.0, D4→5.0, E4→6.0, F4→7.0
print("\nAfter alignment (expected: E4→3.0, C4→4.0, D4→5.0, E4→6.0, F4→7.0):")
offsets_ok = True
notes_after = list(aligned.flatten().getElementsByClass(['Note']))
for n in notes_after:
    print(f"  {n.nameWithOctave} @ offset {n.offset:.2f}")

expected = {3.0, 4.0, 5.0, 6.0, 7.0}
actual_offsets = {n.offset for n in notes_after}
if actual_offsets != expected:
    print(f"\n  FAIL: Expected offsets {sorted(expected)}, got {sorted(actual_offsets)}")
    offsets_ok = False
else:
    print("\n  PASS: Offsets are exactly as expected!")

# Write to musicxml to inspect in MuseScore
ts = music21.meter.TimeSignature("4/4")
for p in aligned.parts:
    p.insert(0, ts)
aligned.makeMeasures(inPlace=True)
aligned.makeNotation(inPlace=True)
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_beat_aligned.musicxml")
aligned.write("musicxml", out_path)
print(f"\n  Written: {out_path}")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 – Real audio downbeat detection
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 2: Real audio — detect_downbeat_offset('test_real.wav')")
print("=" * 60)

audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_real.wav")
if not os.path.exists(audio_path):
    print(f"  SKIP: {audio_path} not found. Upload a test WAV to run this test.")
else:
    # We don't know the tempo ahead of time for the real file, pass 0 to auto-detect
    pickup = detect_downbeat_offset(audio_path, tempo_bpm=0, time_sig_str="4/4")
    print(f"\n  Detected pickup: {pickup:.2f} quarter-lengths")
    if pickup >= 0.0:
        print("  PASS: detect_downbeat_offset returned a valid (non-negative) value.")
    else:
        print("  FAIL: negative pickup returned — check beat_alignment logic.")

print()
print("=" * 60)
print(f"Summary: TEST 1 {'PASSED' if offsets_ok else 'FAILED'}")
print("=" * 60)

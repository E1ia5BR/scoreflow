"""
test_ensemble.py — Tests for ensemble transcription note fusion.

Run: pytest test_ensemble.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import music21
from ensemble import _extract_note_set, _notes_match, _fuse_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_score(notes_data: list[dict]) -> music21.stream.Score:
    """Create a score from a list of {pitch, offset, duration, velocity} dicts."""
    score = music21.stream.Score()
    part = music21.stream.Part()

    for nd in notes_data:
        n = music21.note.Note(nd["pitch"])
        n.quarterLength = nd.get("duration", 1.0)
        n.volume.velocity = nd.get("velocity", 80)
        part.insert(nd.get("offset", 0.0), n)

    score.insert(0, part)
    return score


# ---------------------------------------------------------------------------
# Tests: Note Extraction
# ---------------------------------------------------------------------------

class TestNoteExtraction:
    def test_extracts_notes(self):
        score = _make_score([
            {"pitch": "C4", "offset": 0.0, "duration": 1.0, "velocity": 80},
            {"pitch": "E4", "offset": 1.0, "duration": 1.0, "velocity": 90},
        ])
        notes = _extract_note_set(score)
        assert len(notes) == 2
        assert notes[0]["pitch_midi"] == 60  # C4
        assert notes[1]["pitch_midi"] == 64  # E4

    def test_empty_score(self):
        score = music21.stream.Score()
        part = music21.stream.Part()
        score.insert(0, part)
        notes = _extract_note_set(score)
        assert len(notes) == 0

    def test_extracts_chords(self):
        score = music21.stream.Score()
        part = music21.stream.Part()
        c = music21.chord.Chord(["C4", "E4", "G4"])
        c.quarterLength = 1.0
        c.volume.velocity = 70
        part.insert(0, c)
        score.insert(0, part)

        notes = _extract_note_set(score)
        assert len(notes) == 3


# ---------------------------------------------------------------------------
# Tests: Note Matching
# ---------------------------------------------------------------------------

class TestNoteMatching:
    def test_exact_match(self):
        a = {"pitch_midi": 60, "offset": 0.0}
        b = {"pitch_midi": 60, "offset": 0.0}
        assert _notes_match(a, b) is True

    def test_close_offset_match(self):
        a = {"pitch_midi": 60, "offset": 0.0}
        b = {"pitch_midi": 60, "offset": 0.2}
        assert _notes_match(a, b) is True  # within 0.25 tolerance

    def test_different_pitch_no_match(self):
        a = {"pitch_midi": 60, "offset": 0.0}
        b = {"pitch_midi": 62, "offset": 0.0}
        assert _notes_match(a, b) is False

    def test_far_offset_no_match(self):
        a = {"pitch_midi": 60, "offset": 0.0}
        b = {"pitch_midi": 60, "offset": 1.0}
        assert _notes_match(a, b) is False


# ---------------------------------------------------------------------------
# Tests: Score Fusion
# ---------------------------------------------------------------------------

class TestScoreFusion:
    def test_matching_notes_fused(self):
        """Notes present in both scores should result in high-confidence output."""
        score_a = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 80},
            {"pitch": "E4", "offset": 1.0, "velocity": 80},
        ])
        score_b = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 90},
            {"pitch": "E4", "offset": 1.0, "velocity": 90},
        ])

        fused = _fuse_scores(score_a, score_b)
        notes = list(fused.flatten().notes)
        assert len(notes) == 2

    def test_noise_filtered(self):
        """Very quiet/short notes from only one model should be filtered."""
        score_a = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 80},
        ])
        score_b = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 80},
            # This quiet short note only in B — should be filtered
            {"pitch": "F#3", "offset": 0.5, "velocity": 30, "duration": 0.1},
        ])

        fused = _fuse_scores(score_a, score_b)
        notes = list(fused.flatten().notes)
        # F#3 should be filtered (velocity 30 < 55)
        assert len(notes) == 1

    def test_strong_single_model_note_kept(self):
        """Loud note from one model should be kept."""
        score_a = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 80},
            {"pitch": "G4", "offset": 2.0, "velocity": 90, "duration": 1.0},
        ])
        score_b = _make_score([
            {"pitch": "C4", "offset": 0.0, "velocity": 80},
            # G4 only in A — should be kept (strong enough)
        ])

        fused = _fuse_scores(score_a, score_b)
        notes = list(fused.flatten().notes)
        assert len(notes) == 2

    def test_empty_scores(self):
        score_a = _make_score([])
        score_b = _make_score([])
        fused = _fuse_scores(score_a, score_b)
        notes = list(fused.flatten().notes)
        assert len(notes) == 0

"""
ensemble.py — Ensemble transcription using both Magenta and Basic Pitch.

For piano/polyphonic audio, runs BOTH models and fuses results for higher accuracy:
  - Notes detected by both models → high confidence (kept)
  - Notes detected by only one model → evaluated by velocity/duration
  - Very short/quiet single-model notes → likely noise (removed)

This significantly reduces false positives while retaining real notes.
"""

from __future__ import annotations

import os
import traceback
from typing import Optional

import music21


# Tolerance for matching notes between models (in quarter-lengths)
OFFSET_TOLERANCE = 0.25   # notes within 1/16 QL of each other are "same time"
PITCH_TOLERANCE = 0       # exact pitch match required


def _extract_note_set(score: music21.stream.Score) -> list[dict]:
    """
    Extract a list of note descriptors from a score for comparison.
    Each descriptor: {pitch_midi, offset, duration_ql, velocity}
    """
    notes = []
    for el in score.flatten().notes:
        if isinstance(el, music21.chord.Chord):
            for p in el.pitches:
                notes.append({
                    "pitch_midi": p.midi,
                    "offset": float(el.offset),
                    "duration_ql": float(el.quarterLength),
                    "velocity": int(el.volume.velocity or 80),
                })
        elif isinstance(el, music21.note.Note):
            notes.append({
                "pitch_midi": el.pitch.midi,
                "offset": float(el.offset),
                "duration_ql": float(el.quarterLength),
                "velocity": int(el.volume.velocity or 80),
            })
    return notes


def _notes_match(a: dict, b: dict) -> bool:
    """Check if two note descriptors represent the same musical event."""
    return (
        abs(a["pitch_midi"] - b["pitch_midi"]) <= PITCH_TOLERANCE
        and abs(a["offset"] - b["offset"]) <= OFFSET_TOLERANCE
    )


def _fuse_scores(
    score_a: music21.stream.Score,
    score_b: music21.stream.Score,
    name_a: str = "Magenta",
    name_b: str = "BasicPitch",
) -> music21.stream.Score:
    """
    Fuse two transcription results into one higher-quality score.

    Strategy:
      1. Extract notes from both scores
      2. Find matches (same pitch at ~same time)
      3. Build a new score:
         - Matched notes: keep with averaged velocity/duration (high confidence)
         - Unmatched notes with velocity >= 60 and duration >= 0.25: keep (medium confidence)
         - Unmatched notes below thresholds: discard (likely noise)
    """
    notes_a = _extract_note_set(score_a)
    notes_b = _extract_note_set(score_b)

    print(f"[ensemble] {name_a}: {len(notes_a)} notes, {name_b}: {len(notes_b)} notes", flush=True)

    # Find matches: for each note in A, find best match in B
    matched_b = set()  # indices of B notes already matched
    fused_notes = []

    for a_note in notes_a:
        best_match_idx = None
        best_dist = float("inf")

        for bi, b_note in enumerate(notes_b):
            if bi in matched_b:
                continue
            if _notes_match(a_note, b_note):
                dist = abs(a_note["offset"] - b_note["offset"])
                if dist < best_dist:
                    best_dist = dist
                    best_match_idx = bi

        if best_match_idx is not None:
            # Both models agree — high confidence
            b_note = notes_b[best_match_idx]
            matched_b.add(best_match_idx)
            fused_notes.append({
                "pitch_midi": a_note["pitch_midi"],
                "offset": (a_note["offset"] + b_note["offset"]) / 2,
                "duration_ql": max(a_note["duration_ql"], b_note["duration_ql"]),
                "velocity": (a_note["velocity"] + b_note["velocity"]) // 2,
                "confidence": "high",
            })
        else:
            # Only in model A — keep if strong enough
            if a_note["velocity"] >= 55 and a_note["duration_ql"] >= 0.2:
                fused_notes.append({**a_note, "confidence": "medium"})

    # Check unmatched B notes
    for bi, b_note in enumerate(notes_b):
        if bi not in matched_b:
            if b_note["velocity"] >= 55 and b_note["duration_ql"] >= 0.2:
                fused_notes.append({**b_note, "confidence": "medium"})

    # Sort by offset
    fused_notes.sort(key=lambda n: (n["offset"], n["pitch_midi"]))

    high_count = sum(1 for n in fused_notes if n["confidence"] == "high")
    med_count = sum(1 for n in fused_notes if n["confidence"] == "medium")
    print(
        f"[ensemble] Fused: {len(fused_notes)} notes "
        f"({high_count} high-confidence, {med_count} medium-confidence)",
        flush=True,
    )

    # Build a new music21 score from fused notes
    new_score = music21.stream.Score()
    part = music21.stream.Part()

    for fn in fused_notes:
        n = music21.note.Note(fn["pitch_midi"])
        n.quarterLength = fn["duration_ql"]
        n.volume.velocity = fn["velocity"]
        part.insert(fn["offset"], n)

    new_score.insert(0, part)
    return new_score


def transcribe_ensemble(audio_path: str) -> tuple[music21.stream.Score, list]:
    """
    Run both Magenta and Basic Pitch on the same audio and fuse results.

    Falls back to single-model transcription if one model fails.

    Returns (score, notes_list) — same interface as transcribe_audio_to_score().
    """
    import requests

    audio_path = os.path.abspath(audio_path)
    audio_dir = os.path.dirname(audio_path)
    file_name_without_ext = os.path.splitext(os.path.basename(audio_path))[0]

    score_magenta: Optional[music21.stream.Score] = None
    score_basic: Optional[music21.stream.Score] = None

    # --- Run Magenta ---
    try:
        magenta_url = os.environ.get("MAGENTA_URL", "http://localhost:8002/transcribe")
        midi_path_mag = os.path.join(audio_dir, file_name_without_ext + "_magenta.mid")

        with open(audio_path, "rb") as f:
            resp = requests.post(magenta_url, files={"audio": f}, timeout=600)
        if resp.status_code == 200:
            with open(midi_path_mag, "wb") as f:
                f.write(resp.content)
            score_magenta = music21.converter.parse(midi_path_mag)
            print(f"[ensemble] Magenta: {len(list(score_magenta.flatten().notes))} notes", flush=True)
        else:
            print(f"[ensemble] Magenta failed: HTTP {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[ensemble] Magenta error: {e}", flush=True)

    # --- Run Basic Pitch ---
    try:
        bp_url = os.environ.get("BASIC_PITCH_URL", "http://localhost:8001/transcribe")
        midi_path_bp = os.path.join(audio_dir, file_name_without_ext + "_basic_pitch.mid")

        with open(audio_path, "rb") as f:
            resp = requests.post(bp_url, files={"audio": f}, timeout=600)
        if resp.status_code == 200:
            with open(midi_path_bp, "wb") as f:
                f.write(resp.content)
            score_basic = music21.converter.parse(midi_path_bp)
            print(f"[ensemble] BasicPitch: {len(list(score_basic.flatten().notes))} notes", flush=True)
        else:
            print(f"[ensemble] BasicPitch failed: HTTP {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[ensemble] BasicPitch error: {e}", flush=True)

    # --- Fuse or fallback ---
    if score_magenta and score_basic:
        score = _fuse_scores(score_magenta, score_basic)
    elif score_magenta:
        print("[ensemble] Using Magenta only (BasicPitch unavailable)", flush=True)
        score = score_magenta
    elif score_basic:
        print("[ensemble] Using BasicPitch only (Magenta unavailable)", flush=True)
        score = score_basic
    else:
        raise ValueError("Ensemble transcription failed: both models unavailable")

    notes = list(score.flatten().notes)
    return score, notes

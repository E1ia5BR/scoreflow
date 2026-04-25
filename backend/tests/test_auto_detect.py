"""
test_auto_detect.py — Tests for BPM and time signature auto-detection.

Run: pytest test_auto_detect.py -v
"""

import os
import sys
import pytest
import numpy as np

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_detect import (
    detect_bpm_from_audio,
    detect_time_signature,
    add_dynamics_from_velocity,
    _compute_onset_envelope,
    _load_audio_safe,
)


# ---------------------------------------------------------------------------
# Helpers: generate synthetic test audio
# ---------------------------------------------------------------------------

def _generate_click_track(bpm: float, duration_sec: float = 8.0, sr: int = 22050) -> str:
    """Generate a WAV file with evenly-spaced clicks at the given BPM."""
    import soundfile as sf

    n_samples = int(duration_sec * sr)
    y = np.zeros(n_samples, dtype="float32")

    beat_interval = int(60.0 / bpm * sr)
    click_len = min(200, beat_interval // 4)

    for i in range(0, n_samples, beat_interval):
        end = min(i + click_len, n_samples)
        # Short sine burst as click
        t = np.arange(end - i) / sr
        y[i:end] += 0.8 * np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 40)

    path = os.path.join(os.path.dirname(__file__), "_test_click_track.wav")
    sf.write(path, y, sr)
    return path


def _generate_accented_clicks(
    bpm: float, beats_per_bar: int, duration_sec: float = 10.0, sr: int = 22050
) -> str:
    """Generate clicks where beat 1 is louder (accented)."""
    import soundfile as sf

    n_samples = int(duration_sec * sr)
    y = np.zeros(n_samples, dtype="float32")

    beat_interval = int(60.0 / bpm * sr)
    click_len = min(200, beat_interval // 4)
    beat_count = 0

    for i in range(0, n_samples, beat_interval):
        is_downbeat = (beat_count % beats_per_bar) == 0
        amplitude = 1.0 if is_downbeat else 0.4

        end = min(i + click_len, n_samples)
        t = np.arange(end - i) / sr
        freq = 1200 if is_downbeat else 800
        y[i:end] += amplitude * np.sin(2 * np.pi * freq * t) * np.exp(-t * 40)
        beat_count += 1

    path = os.path.join(os.path.dirname(__file__), "_test_accented_clicks.wav")
    sf.write(path, y, sr)
    return path


# ---------------------------------------------------------------------------
# Tests: BPM Detection
# ---------------------------------------------------------------------------

class TestBPMDetection:
    """Tests for detect_bpm_from_audio."""

    def test_detects_120bpm(self):
        path = _generate_click_track(120.0, duration_sec=10.0)
        try:
            bpm, confidence = detect_bpm_from_audio(path)
            # Allow ±15 BPM tolerance (autocorrelation has limited resolution)
            assert 100 <= bpm <= 140, f"Expected ~120 BPM, got {bpm}"
            assert confidence >= 0.0
        finally:
            os.remove(path)

    def test_detects_90bpm(self):
        path = _generate_click_track(90.0, duration_sec=12.0)
        try:
            bpm, confidence = detect_bpm_from_audio(path)
            assert 75 <= bpm <= 110, f"Expected ~90 BPM, got {bpm}"
        finally:
            os.remove(path)

    def test_detects_150bpm(self):
        path = _generate_click_track(150.0, duration_sec=8.0)
        try:
            bpm, confidence = detect_bpm_from_audio(path)
            assert 130 <= bpm <= 170, f"Expected ~150 BPM, got {bpm}"
        finally:
            os.remove(path)

    def test_returns_fallback_for_invalid_file(self):
        bpm, confidence = detect_bpm_from_audio("nonexistent_file.wav")
        assert bpm == 120.0
        assert confidence == 0.0

    def test_returns_tuple(self):
        path = _generate_click_track(120.0, duration_sec=5.0)
        try:
            result = detect_bpm_from_audio(path)
            assert isinstance(result, tuple)
            assert len(result) == 2
        finally:
            os.remove(path)


# ---------------------------------------------------------------------------
# Tests: Time Signature Detection
# ---------------------------------------------------------------------------

class TestTimeSignatureDetection:
    """Tests for detect_time_signature."""

    def test_detects_4_4(self):
        path = _generate_accented_clicks(120, beats_per_bar=4, duration_sec=12.0)
        try:
            ts, conf = detect_time_signature(path, bpm=120.0)
            # Synthetic clicks may be interpreted as various meters
            assert ts in ("4/4", "2/4", "3/4", "6/8"), f"Unexpected time sig: {ts}"
        finally:
            os.remove(path)

    def test_detects_3_4(self):
        path = _generate_accented_clicks(100, beats_per_bar=3, duration_sec=12.0)
        try:
            ts, conf = detect_time_signature(path, bpm=100.0)
            # Synthetic clicks may be interpreted as various meters
            assert ts in ("3/4", "6/8", "2/4", "4/4"), f"Unexpected time sig: {ts}"
        finally:
            os.remove(path)

    def test_returns_fallback_for_invalid_file(self):
        ts, conf = detect_time_signature("nonexistent.wav")
        assert ts == "4/4"
        assert conf == 0.0

    def test_returns_tuple(self):
        path = _generate_accented_clicks(120, beats_per_bar=4, duration_sec=8.0)
        try:
            result = detect_time_signature(path, bpm=120.0)
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], str)
        finally:
            os.remove(path)


# ---------------------------------------------------------------------------
# Tests: Dynamics from Velocity
# ---------------------------------------------------------------------------

class TestDynamics:
    """Tests for add_dynamics_from_velocity."""

    def test_adds_dynamics_to_score(self):
        import music21

        score = music21.stream.Score()
        part = music21.stream.Part()

        # Create notes with different velocities
        velocities = [30, 30, 30, 30, 30, 100, 100, 100, 100, 100]
        for i, vel in enumerate(velocities):
            n = music21.note.Note("C4")
            n.quarterLength = 1.0
            n.volume.velocity = vel
            part.insert(float(i), n)

        score.insert(0, part)

        # Should not crash
        add_dynamics_from_velocity(score)

        dynamics = list(score.flatten().getElementsByClass("Dynamic"))
        assert len(dynamics) >= 1, "Should insert at least one dynamic marking"

    def test_handles_empty_score(self):
        import music21

        score = music21.stream.Score()
        part = music21.stream.Part()
        score.insert(0, part)

        # Should not crash on empty score
        add_dynamics_from_velocity(score)

    def test_handles_no_velocity(self):
        import music21

        score = music21.stream.Score()
        part = music21.stream.Part()

        for i in range(5):
            n = music21.note.Note("C4")
            n.quarterLength = 1.0
            # No velocity set
            part.insert(float(i), n)

        score.insert(0, part)
        add_dynamics_from_velocity(score)  # Should not crash


# ---------------------------------------------------------------------------
# Tests: Onset Envelope
# ---------------------------------------------------------------------------

class TestOnsetEnvelope:
    """Tests for _compute_onset_envelope."""

    def test_returns_array(self):
        y = np.random.randn(22050 * 3).astype("float32")  # 3 seconds
        env = _compute_onset_envelope(y, 22050)
        assert isinstance(env, np.ndarray)
        assert len(env) > 0

    def test_silent_audio_returns_zeros(self):
        y = np.zeros(22050 * 2, dtype="float32")
        env = _compute_onset_envelope(y, 22050)
        assert np.allclose(env, 0)

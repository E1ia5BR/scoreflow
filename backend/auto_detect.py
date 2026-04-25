"""
auto_detect.py
==============
Detecção automática de BPM e compasso (time signature) diretamente do áudio.

Por que este módulo existe
--------------------------
O pipeline anterior extraía o BPM das MetronomeMarks do MIDI gerado pela IA,
que frequentemente estavam erradas ou ausentes (retornando 0.0 / 120 fallback).
Isso degradava todo o pós-processamento (grade rítmica, desfragmentação, beat
alignment).

Este módulo analisa o ÁUDIO ORIGINAL para detectar:
  1. BPM real (via onset envelope + autocorrelação)
  2. Compasso provável (via padrão de acentuação rítmica)

Ambas as funções são compatíveis com Windows (sem numba, sem soxr).
Usam soundfile + scipy diretamente.
"""

from __future__ import annotations

import math
import traceback
from typing import Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Audio loading helper (Windows-safe: no soxr, no numba)
# ---------------------------------------------------------------------------

TARGET_SR = 22050
HOP = 512
N_FFT = 2048


def _load_audio_safe(audio_path: str) -> Tuple[np.ndarray, int]:
    """
    Load audio as mono float32 at TARGET_SR Hz.
    Uses soundfile + scipy.signal.resample_poly to avoid soxr DLL bug on Windows.
    """
    try:
        import soundfile as sf
        from scipy.signal import resample_poly
        from math import gcd

        y_raw, orig_sr = sf.read(audio_path, dtype="float32", always_2d=False)
        if y_raw.ndim > 1:
            y_raw = y_raw.mean(axis=1)
        if orig_sr != TARGET_SR:
            common = gcd(orig_sr, TARGET_SR)
            y = resample_poly(y_raw, TARGET_SR // common, orig_sr // common)
            y = y.astype("float32")
        else:
            y = y_raw
        return y, TARGET_SR
    except Exception as e:
        print(f"[auto_detect] soundfile load failed ({e}), trying librosa")
        import librosa
        y, sr = librosa.load(audio_path, sr=TARGET_SR, mono=True)
        return y, sr


def _compute_onset_envelope(y: np.ndarray, sr: int) -> np.ndarray:
    """
    Compute onset strength envelope via spectral flux (pure scipy, no numba).
    Returns 1D array of onset strengths per frame.
    """
    from scipy.signal import stft as _stft

    _, _, Zxx = _stft(y, fs=sr, nperseg=N_FFT, noverlap=N_FFT - HOP)
    mag = np.abs(Zxx)
    flux = np.sum(np.maximum(0, np.diff(mag, axis=1)), axis=0)
    return flux


# ---------------------------------------------------------------------------
# 1. BPM Detection
# ---------------------------------------------------------------------------

def detect_bpm_from_audio(audio_path: str) -> Tuple[float, float]:
    """
    Detect BPM directly from the audio file.

    Uses onset envelope autocorrelation to find the dominant tempo.
    Also provides a confidence score (0.0 to 1.0) based on how clear
    the autocorrelation peak is.

    Parameters
    ----------
    audio_path : Path to WAV/MP3 audio file.

    Returns
    -------
    (bpm, confidence) : tuple
        bpm        : Estimated BPM (float). Falls back to 120.0 on failure.
        confidence : 0.0 to 1.0 indicating how strong the tempo estimate is.
    """
    try:
        y, sr = _load_audio_safe(audio_path)
        onset_env = _compute_onset_envelope(y, sr)

        if len(onset_env) < 10:
            print("[auto_detect] Audio too short for BPM detection")
            return 120.0, 0.0

        # Autocorrelation of onset envelope
        ac = np.correlate(onset_env, onset_env, mode='full')
        ac = ac[len(ac) // 2:]  # keep positive lags only

        # Normalize autocorrelation
        if ac[0] > 0:
            ac_norm = ac / ac[0]
        else:
            return 120.0, 0.0

        # BPM range: 40..240 → lag range in frames
        lag_min = max(1, int(60.0 / 240.0 * sr / HOP))
        lag_max = min(int(60.0 / 40.0 * sr / HOP), len(ac) - 1)

        if lag_max <= lag_min:
            return 120.0, 0.0

        # Find the peak in the valid BPM range
        ac_slice = ac_norm[lag_min:lag_max]
        best_idx = int(np.argmax(ac_slice))
        best_lag = best_idx + lag_min
        peak_strength = float(ac_norm[best_lag])

        bpm = 60.0 / (best_lag * HOP / sr)

        # Check for octave errors (common: detected 2x or 0.5x the real tempo)
        # If we find a strong peak at half the tempo, prefer it
        half_lag = best_lag * 2
        if half_lag < len(ac_norm):
            half_strength = float(ac_norm[half_lag])
            # If the half-tempo peak is >70% as strong, the real BPM is probably halved
            if half_strength > peak_strength * 0.7 and bpm > 160:
                bpm = bpm / 2.0
                peak_strength = half_strength
                print(f"[auto_detect] Octave correction: halved BPM to {bpm:.1f}", flush=True)

        # Similarly, check double tempo (slow detections are often half the real tempo)
        double_lag = best_lag // 2
        if double_lag >= lag_min:
            double_strength = float(ac_norm[double_lag])
            if double_strength > peak_strength * 0.7 and bpm < 70:
                bpm = bpm * 2.0
                peak_strength = double_strength
                print(f"[auto_detect] Octave correction: doubled BPM to {bpm:.1f}", flush=True)

        # Snap to nearest 0.1 BPM for cleanliness
        bpm = round(bpm, 1)

        # Confidence: how strong the peak is relative to the mean of the AC slice
        mean_ac = float(np.mean(ac_slice))
        if mean_ac > 0:
            confidence = min(1.0, (peak_strength - mean_ac) / (1.0 - mean_ac + 1e-6))
            confidence = max(0.0, confidence)
        else:
            confidence = peak_strength

        print(f"[auto_detect] BPM detected: {bpm:.1f} (confidence: {confidence:.2f})", flush=True)
        return bpm, confidence

    except Exception:
        print(f"[auto_detect] BPM detection failed:\n{traceback.format_exc()}")
        return 120.0, 0.0


# ---------------------------------------------------------------------------
# 2. Time Signature Detection
# ---------------------------------------------------------------------------

def detect_time_signature(
    audio_path: str,
    bpm: float = 0.0,
) -> Tuple[str, float]:
    """
    Detect the most likely time signature from audio.

    Strategy:
    - Detect beats in the audio
    - Group beats into windows of 2, 3, and 4
    - Measure the accent pattern (energy of 1st beat vs rest)
    - The grouping with strongest accent on beat 1 wins

    Parameters
    ----------
    audio_path : Path to audio file.
    bpm        : Pre-detected BPM. If 0, will estimate from audio.

    Returns
    -------
    (time_sig, confidence) : tuple
        time_sig   : String like "4/4", "3/4", "6/8"
        confidence : 0.0 to 1.0
    """
    try:
        y, sr = _load_audio_safe(audio_path)
        onset_env = _compute_onset_envelope(y, sr)

        if len(onset_env) < 20:
            print("[auto_detect] Audio too short for time signature detection")
            return "4/4", 0.0

        # Get BPM if not provided
        if not bpm or bpm <= 0:
            bpm, _ = detect_bpm_from_audio(audio_path)

        # Find beat positions
        from scipy.signal import find_peaks

        beat_period_frames = max(1, int(round(60.0 / bpm * sr / HOP)))
        min_dist = max(1, int(beat_period_frames * 0.6))
        beat_frames, _ = find_peaks(onset_env, distance=min_dist)

        if len(beat_frames) < 8:
            print("[auto_detect] Too few beats for time signature detection")
            return "4/4", 0.0

        # Get onset strength at each beat
        onset_at_beats = onset_env[beat_frames]

        # Normalize
        max_onset = np.max(onset_at_beats)
        if max_onset > 0:
            onset_at_beats = onset_at_beats / max_onset

        # Test groupings of 2, 3, and 4
        candidates = {
            2: "2/4",
            3: "3/4",
            4: "4/4",
        }

        best_score = -1.0
        best_sig = "4/4"
        scores = {}

        for group_size, sig_str in candidates.items():
            if len(onset_at_beats) < group_size * 2:
                continue

            # Calculate accent ratio for this grouping
            # For each group of N beats, how much stronger is beat 1 vs the rest?
            n_groups = len(onset_at_beats) // group_size
            if n_groups < 2:
                continue

            trimmed = onset_at_beats[:n_groups * group_size]
            groups = trimmed.reshape(n_groups, group_size)

            # Beat 1 strength (average across all groups)
            beat1_strength = float(np.mean(groups[:, 0]))

            # Other beats strength (average)
            other_strength = float(np.mean(groups[:, 1:]))

            # Accent ratio: how much beat 1 stands out
            if other_strength > 0:
                accent_ratio = beat1_strength / other_strength
            else:
                accent_ratio = beat1_strength

            # Variance of beat-1 strengths (lower = more consistent = better)
            beat1_variance = float(np.var(groups[:, 0]))
            consistency_bonus = max(0, 1.0 - beat1_variance)

            score = accent_ratio * (1.0 + consistency_bonus * 0.3)
            scores[sig_str] = score

            if score > best_score:
                best_score = score
                best_sig = sig_str

        # Detect compound meters (6/8, 12/8)
        # 6/8 looks like 3/4 at the beat level but with subdivision in pairs
        if best_sig == "3/4" and bpm > 100:
            # Fast 3/4 is often actually 6/8
            best_sig = "6/8"
            print("[auto_detect] Fast 3/4 reclassified as 6/8", flush=True)

        # Calculate confidence from score separation
        if len(scores) >= 2:
            sorted_scores = sorted(scores.values(), reverse=True)
            if sorted_scores[1] > 0:
                separation = (sorted_scores[0] - sorted_scores[1]) / sorted_scores[0]
            else:
                separation = 1.0
            confidence = min(1.0, separation + 0.3)
        else:
            confidence = 0.5

        print(
            f"[auto_detect] Time signature: {best_sig} "
            f"(confidence: {confidence:.2f}, scores: {scores})",
            flush=True
        )
        return best_sig, confidence

    except Exception:
        print(f"[auto_detect] Time signature detection failed:\n{traceback.format_exc()}")
        return "4/4", 0.0


# ---------------------------------------------------------------------------
# 3. Dynamics from Velocity
# ---------------------------------------------------------------------------

def add_dynamics_from_velocity(score) -> None:
    """
    Analyze MIDI velocity values in the score and insert music21 Dynamic
    markings at points where the dynamic level changes significantly.

    Velocity mapping:
        0-40   → pp
        41-60  → p
        61-80  → mp
        81-100 → mf
        101-115→ f
        116+   → ff

    Only inserts a new dynamic marking when the level CHANGES from the
    previous one, to avoid cluttering the score.

    Modifies the score in-place.
    """
    import music21

    VELOCITY_MAP = [
        (40,  "pp"),
        (60,  "p"),
        (80,  "mp"),
        (100, "mf"),
        (115, "f"),
        (128, "ff"),
    ]

    def _velocity_to_dynamic(vel: int) -> str:
        for threshold, dyn_str in VELOCITY_MAP:
            if vel <= threshold:
                return dyn_str
        return "ff"

    try:
        for part in score.parts:
            current_dynamic = None
            notes_since_change = 0
            velocity_window = []

            flat_notes = list(part.flat.getElementsByClass(['Note', 'Chord']))

            for el in flat_notes:
                # Get velocity
                vel = None
                try:
                    if hasattr(el, 'volume') and el.volume.velocity is not None:
                        vel = int(el.volume.velocity)
                except Exception:
                    pass

                if vel is None:
                    continue

                velocity_window.append(vel)
                notes_since_change += 1

                # Use a sliding window of 3 notes to smooth velocity
                if len(velocity_window) > 3:
                    velocity_window.pop(0)

                avg_vel = int(sum(velocity_window) / len(velocity_window))
                new_dynamic = _velocity_to_dynamic(avg_vel)

                # Insert dynamic only when it changes (with minimum gap of 4 notes)
                if new_dynamic != current_dynamic and notes_since_change >= 4:
                    try:
                        dyn = music21.dynamics.Dynamic(new_dynamic)
                        part.insert(el.offset, dyn)
                        current_dynamic = new_dynamic
                        notes_since_change = 0
                    except Exception:
                        pass

            # Always insert initial dynamic at the start
            if flat_notes and current_dynamic is None:
                try:
                    first_vel = 80  # default
                    if hasattr(flat_notes[0], 'volume') and flat_notes[0].volume.velocity:
                        first_vel = int(flat_notes[0].volume.velocity)
                    dyn_str = _velocity_to_dynamic(first_vel)
                    dyn = music21.dynamics.Dynamic(dyn_str)
                    part.insert(0, dyn)
                except Exception:
                    pass

        n_dynamics = len(list(score.flatten().getElementsByClass('Dynamic')))
        print(f"[auto_detect] Added {n_dynamics} dynamic markings", flush=True)

    except Exception:
        print(f"[auto_detect] Dynamics insertion failed:\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python auto_detect.py <audio_file>")
        sys.exit(1)

    audio_file = sys.argv[1]
    print(f"Analyzing: {audio_file}\n")

    bpm, bpm_conf = detect_bpm_from_audio(audio_file)
    print(f"  BPM: {bpm:.1f} (confidence: {bpm_conf:.2f})\n")

    ts, ts_conf = detect_time_signature(audio_file, bpm)
    print(f"  Time Signature: {ts} (confidence: {ts_conf:.2f})\n")

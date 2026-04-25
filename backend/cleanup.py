"""
cleanup.py — Automated cleanup of temporary and old files.

Functions:
  - cleanup_intermediate_files(job_dir): Removes _norm.wav, _clean.wav after processing
  - cleanup_old_jobs(max_age_days=7): Removes uploads/results older than 7 days
"""

import os
import time
import shutil
import glob


def cleanup_intermediate_files(upload_dir: str) -> int:
    """
    Remove intermediate audio files (_norm.wav, _clean.wav) from a job's upload directory.
    These are generated during pre-processing and no longer needed after transcription.

    Returns the number of files deleted.
    """
    deleted = 0
    patterns = ["*_norm.wav", "*_clean.wav", "*_magenta.mid", "*_basic_pitch.mid"]

    for pattern in patterns:
        for f in glob.glob(os.path.join(upload_dir, pattern)):
            try:
                os.remove(f)
                deleted += 1
            except Exception as e:
                print(f"[cleanup] Failed to delete {f}: {e}", flush=True)

    if deleted > 0:
        print(f"[cleanup] Removed {deleted} intermediate files from {upload_dir}", flush=True)
    return deleted


def cleanup_old_jobs(max_age_days: int = 7) -> int:
    """
    Remove upload and result directories older than max_age_days.
    Called periodically to comply with data retention policy (LGPD).

    Returns the number of directories deleted.
    """
    deleted = 0
    now = time.time()
    cutoff = now - (max_age_days * 86400)

    for base_dir in ["storage/uploads", "storage/results"]:
        if not os.path.exists(base_dir):
            continue

        for entry in os.listdir(base_dir):
            full_path = os.path.join(base_dir, entry)
            if not os.path.isdir(full_path):
                continue

            try:
                # Use modification time of the directory
                mtime = os.path.getmtime(full_path)
                if mtime < cutoff:
                    shutil.rmtree(full_path, ignore_errors=True)
                    deleted += 1
            except Exception as e:
                print(f"[cleanup] Error checking {full_path}: {e}", flush=True)

    if deleted > 0:
        print(f"[cleanup] Removed {deleted} old job directories (>{max_age_days} days)", flush=True)

    # Also clean up history.json entries for deleted jobs
    try:
        import json
        history_file = "storage/history.json"
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                history = json.load(f)

            # Filter out entries whose result dirs no longer exist
            history = [h for h in history if os.path.exists(os.path.join("storage", "results", h["id"]))]

            with open(history_file, "w") as f:
                json.dump(history, f)
    except Exception:
        pass

    return deleted


if __name__ == "__main__":
    print("Running cleanup...")
    n = cleanup_old_jobs(max_age_days=7)
    print(f"Done. Removed {n} old directories.")

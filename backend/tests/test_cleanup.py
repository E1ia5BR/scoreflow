"""
test_cleanup.py — Tests for file cleanup utilities.

Run: pytest test_cleanup.py -v
"""

import os
import sys
import time
import tempfile
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleanup import cleanup_intermediate_files, cleanup_old_jobs


class TestIntermediateCleanup:
    def test_removes_intermediate_files(self, tmp_path):
        # Create fake intermediate files
        (tmp_path / "audio_norm.wav").write_bytes(b"fake")
        (tmp_path / "audio_clean.wav").write_bytes(b"fake")
        (tmp_path / "audio_magenta.mid").write_bytes(b"fake")
        (tmp_path / "original.wav").write_bytes(b"keep")

        deleted = cleanup_intermediate_files(str(tmp_path))
        assert deleted == 3

        # Original should still exist
        assert (tmp_path / "original.wav").exists()
        # Intermediates should be gone
        assert not (tmp_path / "audio_norm.wav").exists()
        assert not (tmp_path / "audio_clean.wav").exists()

    def test_handles_empty_directory(self, tmp_path):
        deleted = cleanup_intermediate_files(str(tmp_path))
        assert deleted == 0

    def test_handles_nonexistent_directory(self):
        deleted = cleanup_intermediate_files("/nonexistent/path/12345")
        assert deleted == 0


class TestOldJobCleanup:
    def test_removes_old_directories(self, tmp_path, monkeypatch):
        # Create storage structure
        uploads = tmp_path / "storage" / "uploads"
        results = tmp_path / "storage" / "results"
        uploads.mkdir(parents=True)
        results.mkdir(parents=True)

        # Create an "old" job (modify time to 10 days ago)
        old_job = uploads / "old-job-id"
        old_job.mkdir()
        (old_job / "file.wav").write_bytes(b"old")
        old_time = time.time() - (10 * 86400)
        os.utime(str(old_job), (old_time, old_time))

        # Create a "recent" job
        new_job = uploads / "new-job-id"
        new_job.mkdir()
        (new_job / "file.wav").write_bytes(b"new")

        # Monkeypatch to use tmp_path
        monkeypatch.chdir(tmp_path)

        deleted = cleanup_old_jobs(max_age_days=7)
        assert deleted >= 1
        assert not old_job.exists()
        assert new_job.exists()

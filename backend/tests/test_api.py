"""
test_api.py — Tests for the FastAPI endpoints.

Run: pytest test_api.py -v
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestRootEndpoint:
    def test_root_returns_ok(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "ScoreFlow" in data["service"]


class TestJobStatus:
    def test_unknown_job_returns_default(self):
        resp = client.get("/api/jobs/nonexistent-id/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "progress" in data

    def test_job_result_returns_paths(self):
        resp = client.get("/api/jobs/test-id-123/result")
        assert resp.status_code == 200
        data = resp.json()
        assert "musicxml" in data
        assert "midi" in data
        assert "log" in data


class TestHistory:
    def test_history_returns_list(self):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestDeleteJob:
    def test_delete_nonexistent_job(self):
        resp = client.delete("/api/jobs/nonexistent-delete-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == "nonexistent-delete-test"


class TestUploadValidation:
    def test_rejects_invalid_format(self):
        # Upload a .txt file — should be rejected
        resp = client.post(
            "/api/upload",
            data={"time_signature": "4/4", "audio_type": "piano"},
            files={"file": ("test.txt", b"not audio", "text/plain")},
        )
        assert resp.status_code == 400

    def test_accepts_wav(self):
        # Upload a minimal WAV — should be accepted (even if processing fails)
        # Minimal WAV header
        wav_header = b'RIFF' + b'\x24\x00\x00\x00' + b'WAVE'
        wav_header += b'fmt ' + b'\x10\x00\x00\x00' + b'\x01\x00\x01\x00'
        wav_header += b'\x44\xac\x00\x00' + b'\x88\x58\x01\x00'
        wav_header += b'\x02\x00\x10\x00'
        wav_header += b'data' + b'\x00\x00\x00\x00'

        resp = client.post(
            "/api/upload",
            data={"time_signature": "auto", "audio_type": "piano"},
            files={"file": ("test.wav", wav_header, "audio/wav")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data

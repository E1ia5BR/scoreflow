import requests
import time
import os

import sys
test_file_path = sys.argv[1] if len(sys.argv) > 1 else "test_real.wav"

with open(test_file_path, "rb") as f:
    res = requests.post("http://127.0.0.1:8000/api/upload", files={"file": ("test.mp3", f)})
job_id = res.json()["job_id"]
print("Job ID:", job_id)

for i in range(15):
    res_status = requests.get(f"http://127.0.0.1:8000/api/jobs/{job_id}/status")
    print(res_status.json())
    time.sleep(2)

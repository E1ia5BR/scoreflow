FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    sox \
    libsox-fmt-all \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Generate a fake python-rtmidi 1.1.2 package to bypass magenta's broken dependency constraint.
RUN mkdir -p /tmp/fake_rtmidi && \
    echo "from setuptools import setup; setup(name='python-rtmidi', version='1.1.2')" > /tmp/fake_rtmidi/setup.py && \
    pip install /tmp/fake_rtmidi && \
    rm -rf /tmp/fake_rtmidi

# Download Magenta Onsets and Frames pre-trained model
RUN mkdir -p /opt/model && \
    wget -qO /tmp/maestro_checkpoint.zip "https://storage.googleapis.com/magentadata/models/onsets_frames_transcription/maestro_checkpoint.zip" && \
    unzip -q /tmp/maestro_checkpoint.zip -d /opt/model/ && \
    rm /tmp/maestro_checkpoint.zip

# Install Magenta and FastAPI dependencies
RUN pip install --no-cache-dir \
    magenta \
    fastapi \
    uvicorn[standard] \
    python-multipart \
    soundfile

COPY magenta_api.py .

EXPOSE 8002

CMD ["uvicorn", "magenta_api:app", "--host", "0.0.0.0", "--port", "8002"]

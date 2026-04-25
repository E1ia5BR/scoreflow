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
# This avoids compiling outdated cython/c++ code that fails on modern GCC and Python 3.10.
RUN mkdir -p /tmp/fake_rtmidi && \
    echo "from setuptools import setup; setup(name='python-rtmidi', version='1.1.2')" > /tmp/fake_rtmidi/setup.py && \
    pip install /tmp/fake_rtmidi && \
    rm -rf /tmp/fake_rtmidi

# Download Magenta Onsets and Frames pre-trained model
RUN mkdir -p /opt/model && \
    wget -qO /tmp/maestro_checkpoint.zip "https://storage.googleapis.com/magentadata/models/onsets_frames_transcription/maestro_checkpoint.zip" && \
    unzip -q /tmp/maestro_checkpoint.zip -d /opt/model/ && \
    rm /tmp/maestro_checkpoint.zip

# Generate a fake python-rtmidi 1.1.2 package to bypass magenta's broken dependency constraint.
# This avoids compiling outdated cython/c++ code that fails on modern GCC and Python 3.10.
RUN mkdir -p /tmp/fake_rtmidi && \
    echo "from setuptools import setup; setup(name='python-rtmidi', version='1.1.2')" > /tmp/fake_rtmidi/setup.py && \
    pip install /tmp/fake_rtmidi && \
    rm -rf /tmp/fake_rtmidi

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Set PYTHONPATH so that the modules can be discovered easily
ENV PYTHONPATH=/app

# Create storage directories
RUN mkdir -p storage/results

EXPOSE 8000

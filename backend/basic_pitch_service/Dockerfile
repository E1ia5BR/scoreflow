FROM python:3.10-slim

# Install necessary system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    sox \
    libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Basic Pitch and FastAPI dependencies for the microservice
RUN pip install --no-cache-dir "basic-pitch[tf]" fastapi uvicorn python-multipart && \
    pip uninstall -y tflite-runtime || true

# Copy the microservice code
COPY . .

# Expose the API port
EXPOSE 8001

CMD ["uvicorn", "basic_pitch_api:app", "--host", "0.0.0.0", "--port", "8001"]

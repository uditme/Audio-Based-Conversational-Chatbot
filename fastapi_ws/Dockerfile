FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install ffmpeg
# RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
# Install unzip and wget
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    build-essential \
    ffmpeg \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Download Vosk Model
RUN mkdir /opt/vosk-model \
    && wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip \
    && unzip vosk-model-small-en-us-0.15.zip -d /opt/vosk-model \
    && mv /opt/vosk-model/vosk-model-small-en-us-0.15 /opt/vosk-model/model \
    && rm vosk-model-small-en-us-0.15.zip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

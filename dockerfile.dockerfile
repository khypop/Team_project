FROM python:3.10-slim

# GStreamer 및 필수 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-libav libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ./app .

# 기존에 쓰던 라이브러리들 설치
RUN pip install fastapi uvicorn websockets aiortc numpy opencv-python

CMD ["uvicorn", "main.py", "--host", "0.0.0.0", "--port", "8000"]
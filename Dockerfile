FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
ffmpeg \
nodejs \
&& rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY helper.py .
COPY index.html .
COPY static/ ./static/

COPY cookies.txt ./cookies.txt

RUN mkdir -p downloads/YT downloads/SPOTIFY downloads/SAAVN

EXPOSE 10000

CMD ["python", "main.py"]
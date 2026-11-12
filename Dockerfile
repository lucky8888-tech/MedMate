# SafeDose production image.
# Uses Python 3.12 slim and installs the Tesseract OCR engine for the scan feature.
FROM python:3.12-slim

# Tesseract OCR engine (required by the camera/scan feature)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Hosting platforms (Render/Heroku/Railway) inject a PORT env var; default 10000.
ENV PORT=10000
EXPOSE 10000

# gunicorn runs the Flask app as a production WSGI server.
# Shell form so ${PORT} expands at runtime.
CMD gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120 app:app

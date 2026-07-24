# Apple Vision OCR Service

A standalone HTTP microservice that exposes Apple's Vision framework text recognition for use by the MedAid Django backend.

> **macOS only.** This service uses Apple's native Vision framework via PyObjC and will not run on Linux or Windows.

## Prerequisites

- macOS 13 (Ventura) or later
- Python 3.10+
- Xcode Command Line Tools (`xcode-select --install`)

## Setup

```bash
cd ocr-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

### Development

```bash
# Without authentication (dev mode)
python ocr_server.py

# With authentication
OCR_SERVICE_KEY=your-secret-key python ocr_server.py

# Custom port (default 5050)
OCR_SERVICE_PORT=8080 OCR_SERVICE_KEY=your-secret python ocr_server.py
```

### Production

```bash
OCR_SERVICE_KEY=your-secret gunicorn -w 2 -b 0.0.0.0:5050 ocr_server:app
```

## API

### `GET /health`

Health check endpoint. No authentication required.

**Response:**
```json
{
  "status": "ok",
  "vision_available": true
}
```

### `POST /ocr`

Extract text from an uploaded image or PDF.

**Headers:**
- `X-OCR-Key: your-secret-key` (required if `OCR_SERVICE_KEY` is set)

**Body:** `multipart/form-data` with a `file` field.

**Supported file types:**
- Images: JPEG, PNG, WebP, TIFF, BMP, GIF
- Documents: PDF (rasterized at 300 DPI per page)

**Response:**
```json
{
  "text": "Full extracted text with newlines between blocks",
  "confidence": 0.95,
  "blocks": [
    {
      "text": "Individual text block",
      "confidence": 0.97,
      "bbox": [0.1, 0.2, 0.8, 0.05]
    }
  ],
  "pages": 1
}
```

**Error responses:**
- `400` — No file provided or empty file
- `401` — Invalid or missing `X-OCR-Key`
- `415` — Unsupported file type
- `500` — Vision OCR processing failure
- `503` — Vision framework not available

## Architecture

```
Django Backend  ──HTTP──►  OCR Service (this)  ──PyObjC──►  Apple Vision
                              port 5050
```

The Django backend calls this service via `OCR_SERVICE_URL` + `OCR_SERVICE_KEY` settings. If this service is unreachable, the backend falls back to Tesseract, then to the NVIDIA vision model.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OCR_SERVICE_PORT` | `5050` | Port to listen on |
| `OCR_SERVICE_KEY` | *(empty)* | Shared secret for `X-OCR-Key` auth. If empty, auth is disabled (dev mode). |

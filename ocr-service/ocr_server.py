"""
Apple Vision OCR HTTP microservice.

Exposes Apple's Vision framework text recognition over HTTP for use by the
Django backend. Must run on macOS hardware.

Endpoints:
    GET  /health  — Health check
    POST /ocr     — OCR a file (image or PDF)
"""

import logging
import os
import time

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ocr_service")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)

OCR_SERVICE_KEY = os.environ.get("OCR_SERVICE_KEY", "")
if not OCR_SERVICE_KEY:
    logger.warning("OCR_SERVICE_KEY not set — running without authentication (dev mode)")

# Import Vision OCR module
try:
    from vision_ocr import ocr_file, VISION_AVAILABLE
except ImportError:
    VISION_AVAILABLE = False
    ocr_file = None
    logger.error("Could not import vision_ocr module")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _check_auth():
    """Validate the X-OCR-Key header if OCR_SERVICE_KEY is configured."""
    if not OCR_SERVICE_KEY:
        return None  # No auth configured (dev mode)

    provided_key = request.headers.get("X-OCR-Key", "")
    if provided_key != OCR_SERVICE_KEY:
        return jsonify({"error": "Unauthorized — invalid or missing X-OCR-Key"}), 401

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "vision_available": VISION_AVAILABLE,
    })


@app.route("/ocr", methods=["POST"])
def ocr():
    """
    OCR a file upload.

    Expects multipart/form-data with a 'file' field.
    Returns JSON with extracted text, confidence, and block details.
    """
    # Auth check
    auth_error = _check_auth()
    if auth_error:
        return auth_error

    # Check Vision availability
    if not VISION_AVAILABLE or ocr_file is None:
        return jsonify({
            "error": "Apple Vision framework not available on this system"
        }), 503

    # Validate file
    if "file" not in request.files:
        return jsonify({"error": "No 'file' field in upload"}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty file upload"}), 400

    content_type = uploaded.content_type or ""
    content_type_lower = content_type.lower()

    # Validate content type
    allowed = content_type_lower.startswith("image/") or "pdf" in content_type_lower
    if not allowed:
        # Try to infer from extension
        filename_lower = (uploaded.filename or "").lower()
        if filename_lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp", ".gif")):
            content_type = "image/jpeg"  # default image type
        elif filename_lower.endswith(".pdf"):
            content_type = "application/pdf"
        else:
            return jsonify({
                "error": f"Unsupported file type: {content_type}. Upload an image or PDF."
            }), 415

    # Read file bytes
    file_bytes = uploaded.read()
    file_size = len(file_bytes)

    if file_size == 0:
        return jsonify({"error": "Empty file"}), 400

    logger.info(
        "ocr.request_received",
        extra={
            "filename": uploaded.filename,
            "content_type": content_type,
            "size_bytes": file_size,
        },
    )

    # Run OCR
    start = time.time()
    try:
        result = ocr_file(file_bytes, content_type)
    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            "ocr.processing_failed",
            extra={
                "filename": uploaded.filename,
                "elapsed_s": round(elapsed, 2),
                "error": str(e),
            },
        )
        return jsonify({"error": f"OCR processing failed: {str(e)}"}), 500

    elapsed = time.time() - start
    logger.info(
        "ocr.request_completed",
        extra={
            "filename": uploaded.filename,
            "elapsed_s": round(elapsed, 2),
            "pages": result.get("pages", 1),
            "blocks": len(result.get("blocks", [])),
            "text_length": len(result.get("text", "")),
            "confidence": result.get("confidence", 0.0),
        },
    )

    return jsonify(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("OCR_SERVICE_PORT", 5050))
    logger.info(f"Starting OCR service on port {port}")
    logger.info(f"Vision framework available: {VISION_AVAILABLE}")
    app.run(host="0.0.0.0", port=port, debug=False)

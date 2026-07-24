"""
Apple Vision OCR wrapper using PyObjC.

Provides text extraction from images and PDFs using macOS Vision framework
with VNRecognizeTextRequest at accurate recognition level.

This module MUST run on macOS with PyObjC installed.
"""

import io
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework availability check
# ---------------------------------------------------------------------------
VISION_AVAILABLE = False

try:
    import Vision
    import Quartz
    from Foundation import NSData
    VISION_AVAILABLE = True
    logger.info("vision_ocr.frameworks_loaded")
except ImportError as e:
    logger.warning("vision_ocr.frameworks_unavailable", extra={"error": str(e)})


def _sort_observations(observations) -> list:
    """
    Sort VNRecognizedTextObservation results top-to-bottom, left-to-right.

    Vision uses a coordinate system where the origin is at the bottom-left,
    so we sort by (1 - y) descending (top first), then x ascending (left first).
    """
    items = []
    for obs in observations:
        bbox = obs.boundingBox()
        # bbox is a CGRect: (origin.x, origin.y, size.width, size.height)
        x = bbox.origin.x
        y = bbox.origin.y
        w = bbox.size.width
        h = bbox.size.height
        items.append((obs, x, y, w, h))

    # Sort: top-to-bottom (higher y = higher on page in Vision coords, so descending y),
    # then left-to-right (ascending x)
    items.sort(key=lambda item: (-item[2], item[1]))
    return items


def ocr_image(image_data: bytes) -> Dict:
    """
    Run OCR on a single image using Apple Vision.

    Args:
        image_data: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        {
            "text": "full text with newlines between blocks",
            "confidence": 0.95,  # mean confidence
            "blocks": [{"text": "...", "confidence": 0.97, "bbox": [x, y, w, h]}]
        }
    """
    if not VISION_AVAILABLE:
        raise RuntimeError("Apple Vision framework not available. This must run on macOS.")

    ns_data = NSData.dataWithBytes_length_(image_data, len(image_data))

    # Create image request handler
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(ns_data, None)

    # Create text recognition request
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    # Perform the request
    success, error = handler.performRequests_error_([request], None)
    if not success:
        error_msg = str(error) if error else "Unknown Vision error"
        raise RuntimeError(f"Vision OCR failed: {error_msg}")

    results = request.results() or []

    # Sort observations in reading order
    sorted_items = _sort_observations(results)

    blocks = []
    confidences = []

    for obs, x, y, w, h in sorted_items:
        # Get the top candidate
        candidates = obs.topCandidates_(1)
        if not candidates or len(candidates) == 0:
            continue

        candidate = candidates[0]
        text = candidate.string()
        confidence = candidate.confidence()

        if text and text.strip():
            blocks.append({
                "text": text.strip(),
                "confidence": round(float(confidence), 4),
                "bbox": [round(float(x), 4), round(float(y), 4),
                         round(float(w), 4), round(float(h), 4)],
            })
            confidences.append(float(confidence))

    full_text = "\n".join(block["text"] for block in blocks)
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "text": full_text,
        "confidence": round(mean_confidence, 4),
        "blocks": blocks,
    }


def _rasterize_pdf_page(pdf_doc, page_index: int, dpi: int = 300) -> bytes:
    """
    Rasterize a single PDF page to PNG bytes using Quartz.

    Args:
        pdf_doc: CGPDFDocument reference
        page_index: 1-based page index
        dpi: Target DPI for rasterization

    Returns:
        PNG image bytes
    """
    page = Quartz.CGPDFDocumentGetPage(pdf_doc, page_index)
    if page is None:
        raise RuntimeError(f"Could not get PDF page {page_index}")

    # Get page dimensions in points (72 points per inch)
    page_rect = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
    scale = dpi / 72.0
    width = int(page_rect.size.width * scale)
    height = int(page_rect.size.height * scale)

    # Create bitmap context
    color_space = Quartz.CGColorSpaceCreateDeviceRGB()
    context = Quartz.CGBitmapContextCreate(
        None,  # data (auto-allocate)
        width,
        height,
        8,  # bits per component
        width * 4,  # bytes per row
        color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )

    if context is None:
        raise RuntimeError(f"Could not create bitmap context for page {page_index}")

    # Fill with white background
    Quartz.CGContextSetRGBFillColor(context, 1.0, 1.0, 1.0, 1.0)
    Quartz.CGContextFillRect(context, Quartz.CGRectMake(0, 0, width, height))

    # Scale and draw the page
    Quartz.CGContextScaleCTM(context, scale, scale)
    Quartz.CGContextDrawPDFPage(context, page)

    # Get the image
    cg_image = Quartz.CGBitmapContextCreateImage(context)
    if cg_image is None:
        raise RuntimeError(f"Could not create image from context for page {page_index}")

    # Convert CGImage to PNG data
    from AppKit import NSBitmapImageRep, NSPNGFileType
    bitmap_rep = NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
    png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, {})

    return bytes(png_data)


def ocr_pdf(pdf_data: bytes, dpi: int = 300) -> Dict:
    """
    OCR all pages of a PDF document.

    Rasterizes each page using Quartz, runs Vision OCR on each page image,
    and concatenates results with page break markers.

    Args:
        pdf_data: Raw PDF file bytes
        dpi: DPI for page rasterization (default 300)

    Returns:
        Same structure as ocr_image, with page breaks and page count.
    """
    if not VISION_AVAILABLE:
        raise RuntimeError("Apple Vision framework not available. This must run on macOS.")

    # Load PDF from data
    ns_data = NSData.dataWithBytes_length_(pdf_data, len(pdf_data))
    data_provider = Quartz.CGDataProviderCreateWithCFData(ns_data)
    pdf_doc = Quartz.CGPDFDocumentCreateWithProvider(data_provider)

    if pdf_doc is None:
        raise RuntimeError("Could not open PDF document")

    page_count = Quartz.CGPDFDocumentGetNumberOfPages(pdf_doc)
    if page_count == 0:
        return {
            "text": "",
            "confidence": 0.0,
            "blocks": [],
            "pages": 0,
        }

    all_blocks = []
    page_texts = []
    all_confidences = []

    for page_num in range(1, page_count + 1):
        try:
            page_image_bytes = _rasterize_pdf_page(pdf_doc, page_num, dpi)
            page_result = ocr_image(page_image_bytes)

            page_texts.append(page_result["text"])
            all_blocks.extend(page_result["blocks"])
            if page_result["confidence"] > 0:
                all_confidences.append(page_result["confidence"])

        except Exception as e:
            logger.warning(
                "vision_ocr.page_failed",
                extra={"page": page_num, "error": str(e)},
            )
            page_texts.append(f"[OCR failed for page {page_num}]")

    full_text = "\n--- PAGE BREAK ---\n".join(page_texts)
    mean_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return {
        "text": full_text,
        "confidence": round(mean_confidence, 4),
        "blocks": all_blocks,
        "pages": page_count,
    }


def ocr_file(file_data: bytes, content_type: str) -> Dict:
    """
    OCR a file (image or PDF).

    Args:
        file_data: Raw file bytes
        content_type: MIME type (e.g., "image/jpeg", "application/pdf")

    Returns:
        {
            "text": "...",
            "confidence": 0.95,
            "blocks": [...],
            "pages": 1
        }
    """
    content_type_lower = (content_type or "").lower()

    if "pdf" in content_type_lower:
        result = ocr_pdf(file_data)
    else:
        result = ocr_image(file_data)
        result["pages"] = 1

    return result

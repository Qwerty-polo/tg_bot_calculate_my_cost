"""OCR service.

Supports two engines selected via ``OCR_ENGINE``:
- ``tesseract`` (default): uses pytesseract, lightweight, needs the system
  ``tesseract-ocr`` binary installed.
- ``easyocr``: deep-learning engine, heavier (pulls in torch), better on noisy
  screenshots. Loaded lazily so it is only required when selected.
"""

from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image, ImageFilter, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

_easyocr_reader = None  # cached easyocr.Reader


def _preprocess(image: Image.Image) -> Image.Image:
    """Light preprocessing to improve OCR accuracy on banking screenshots."""
    gray = ImageOps.grayscale(image)
    # Upscale small images, then sharpen for crisper glyph edges.
    if gray.width < 1000:
        scale = 1000 / gray.width
        gray = gray.resize((int(gray.width * scale), int(gray.height * scale)))
    gray = gray.filter(ImageFilter.SHARPEN)
    return ImageOps.autocontrast(gray)


def _extract_tesseract(image_bytes: bytes) -> str:
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = r'D:\Teseract\tesseract.exe'
    image = Image.open(io.BytesIO(image_bytes))
    processed = _preprocess(image)
    lang = settings.ocr_languages or "eng"
    try:
        return pytesseract.image_to_string(processed, lang=lang)
    except pytesseract.TesseractError:
        # Requested language data may be missing; fall back to English.
        logger.warning("Tesseract language '%s' unavailable, falling back to eng", lang)
        return pytesseract.image_to_string(processed, lang="eng")


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr  # type: ignore[import-untyped]

        langs = [
            chunk.strip()
            for chunk in settings.ocr_languages.replace("+", ",").split(",")
            if chunk.strip()
        ] or ["en"]
        # easyocr uses ISO-639-1-ish codes ("en", "uk").
        langs = ["en" if x in {"eng"} else "uk" if x in {"ukr"} else x for x in langs]
        _easyocr_reader = easyocr.Reader(langs, gpu=False)
    return _easyocr_reader


def _extract_easyocr(image_bytes: bytes) -> str:
    reader = _get_easyocr_reader()
    results = reader.readtext(image_bytes, detail=0, paragraph=True)
    return "\n".join(results)


def _extract_sync(image_bytes: bytes) -> str:
    if settings.ocr_engine == "easyocr":
        return _extract_easyocr(image_bytes)
    return _extract_tesseract(image_bytes)


async def extract_text(image_bytes: bytes) -> str:
    """Extract text from image bytes without blocking the event loop."""
    text = await asyncio.to_thread(_extract_sync, image_bytes)
    cleaned = text.strip()
    logger.debug("OCR extracted %d characters using %s", len(cleaned), settings.ocr_engine)
    return cleaned

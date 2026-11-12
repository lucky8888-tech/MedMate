"""
scan.py - OCR text extraction for the SafeDose Camera/Scan feature.

This module isolates image handling and OCR (pytesseract + Pillow) from the
core engine so the rest of the application keeps working even if the OCR
dependencies or the Tesseract binary are not installed.

SafeDose identifies medicines from PRINTED TEXT on the label only. It never
identifies a medicine by colour, shape, or appearance.
"""
import io

try:
    from PIL import Image, ImageOps
    import pytesseract
    try:
        _RESAMPLE = Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9.1
        _RESAMPLE = Image.LANCZOS
    _OCR_AVAILABLE = True
except Exception:
    Image = None
    ImageOps = None
    pytesseract = None
    _RESAMPLE = None
    _OCR_AVAILABLE = False


def is_ocr_available():
    """True if the pytesseract + Pillow Python packages are importable."""
    return _OCR_AVAILABLE


def tesseract_ready():
    """True if the Tesseract OCR binary can actually be invoked."""
    if not _OCR_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess(image_bytes):
    """Open image bytes and apply preprocessing to improve OCR on labels."""
    img = Image.open(io.BytesIO(image_bytes))
    # Grayscale for cleaner text recognition
    img = img.convert("L")
    # Stretch contrast (helps with uneven lighting / glare on foil strips)
    img = ImageOps.autocontrast(img)
    # Upscale small phone photos so tiny label text is legible to OCR
    w, h = img.size
    if max(w, h) < 1200:
        scale = 1200 / float(max(w, h))
        img = img.resize((int(w * scale), int(h * scale)), _RESAMPLE)
    return img


def extract_text(image_bytes):
    """
    Run OCR on the supplied image bytes.

    Returns a dict:
      - available (bool): whether OCR libraries are installed
      - binary_ready (bool): whether the Tesseract binary is callable
      - text (str): recognized text
      - confidence (int): 0-100 estimated average word confidence
      - error (str|None): error message if OCR could not complete
    """
    if not _OCR_AVAILABLE:
        return {
            "available": False,
            "binary_ready": False,
            "text": "",
            "confidence": 0,
            "error": "OCR libraries (pytesseract/Pillow) are not installed.",
        }

    if not tesseract_ready():
        return {
            "available": True,
            "binary_ready": False,
            "text": "",
            "confidence": 0,
            "error": ("Tesseract OCR binary not found. Install the Tesseract OCR "
                      "engine and ensure it is on your system PATH."),
        }

    try:
        img = _preprocess(image_bytes)
    except Exception as e:
        return {
            "available": True,
            "binary_ready": True,
            "text": "",
            "confidence": 0,
            "error": f"Could not read image file: {e}",
        }

    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        return {
            "available": True,
            "binary_ready": True,
            "text": "",
            "confidence": 0,
            "error": f"OCR processing failed: {e}",
        }

    # Reconstruct text and compute average confidence over recognized words
    words = []
    confs = []
    texts = data.get("text", [])
    confs_raw = data.get("conf", [])
    for i, txt in enumerate(texts):
        txt = (txt or "").strip()
        if not txt:
            continue
        try:
            c = float(confs_raw[i])
        except (ValueError, TypeError, IndexError):
            c = -1.0
        if c >= 0:
            confs.append(c)
        words.append(txt)

    text = " ".join(words)
    confidence = int(round(sum(confs) / len(confs))) if confs else 0

    return {
        "available": True,
        "binary_ready": True,
        "text": text,
        "confidence": confidence,
        "error": None,
    }

"""File checks and PDF text extraction. Files stay in memory and are never saved."""
import io
from pypdf import PdfReader

MAX_BYTES = 4 * 1024 * 1024
MAX_PDF_PAGES = 3
MIN_TEXT_CHARS = 200   # below this, treat the PDF as scanned


class IntakeError(ValueError):
    pass


def sniff(data: bytes) -> str:
    """Detect the file type from its content, not its name."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise IntakeError("Please upload a PDF, JPG, PNG or WEBP file.")


def check(data: bytes) -> str:
    if not data:
        raise IntakeError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise IntakeError("The file is larger than 4 MB. Try a smaller photo or a PDF.")
    return sniff(data)


def pdf_text(data: bytes) -> str:
    """Text layer of the first pages, or '' if the PDF is scanned or unreadable."""
    try:
        r = PdfReader(io.BytesIO(data))
        if r.is_encrypted:
            return ""
        text = "\n".join((p.extract_text() or "") for p in r.pages[:MAX_PDF_PAGES])
    except Exception:
        return ""
    return text if len(text.strip()) >= MIN_TEXT_CHARS else ""

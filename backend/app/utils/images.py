"""Image validation + safe storage. The client filename is never trusted."""
import os
import uuid

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

MAGIC_BYTES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"RIFF": ".webp",  # full WEBP check needs bytes 8:12 == b"WEBP"
}


def detect_extension(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"RIFF") and len(head) >= 12 and head[8:12] == b"WEBP":
        return ".webp"
    return None


def validate_image(content: bytes, content_type: str | None, max_bytes: int) -> str:
    """Returns the safe extension. Raises ValueError on any problem."""
    if not content:
        raise ValueError("Empty file")
    if len(content) > max_bytes:
        raise ValueError(f"Image too large ({len(content)} bytes, max {max_bytes})")
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported media type: {content_type}")
    ext = detect_extension(content[:12])
    if ext is None:
        raise ValueError("File content is not a supported image (JPEG/PNG/WEBP)")
    return ext


def safe_filename(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path

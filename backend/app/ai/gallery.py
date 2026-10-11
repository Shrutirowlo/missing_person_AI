"""Registered-gallery authority: data/registered/ folder names.

The ORIGINAL registered-person dataset is the directory
<MPP_ORIGINAL_ROOT>/data/registered/, containing one folder per identity.
This module ONLY lists that directory (read-only) and maps a model
prediction to a gallery identity by exact folder-name match.

It contains no AI logic, creates no gallery, and never invents
identities: a predicted label with no corresponding folder maps to None
with an explicit reason.
"""
import os
import threading

SUPPORTED_PHOTO_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

_cache: frozenset | None = None
_lock = threading.Lock()
_photo_cache: dict = {}


def gallery_dir() -> str:
    return os.path.join(
        os.getenv("MPP_ORIGINAL_ROOT", r"C:/Users/shrut_hi39oyy/Downloads/mpp/mpp"),
        "data",
        "registered",
    )


def identities() -> frozenset:
    """Folder names in data/registered/ (empty set if dir unreadable)."""
    global _cache
    with _lock:
        if _cache is None:
            try:
                entries = os.listdir(gallery_dir())
            except OSError:
                entries = []
            _cache = frozenset(
                e for e in entries
                if os.path.isdir(os.path.join(gallery_dir(), e))
            )
        return _cache


def image_count(identity: str) -> int:
    try:
        return sum(
            1 for e in os.listdir(os.path.join(gallery_dir(), identity))
            if os.path.isfile(os.path.join(gallery_dir(), identity, e))
        )
    except OSError:
        return 0


def invalidate(identity: str | None = None) -> None:
    """Drop cached listings so newly stored photos are visible immediately."""
    global _cache
    with _lock:
        _cache = None
    if identity:
        _photo_cache.pop(identity, None)
    else:
        _photo_cache.clear()


def registered_match(label: str | None) -> tuple[str | None, str | None]:
    """Maps a model prediction to a gallery identity.

    Returns (identity, None) on exact folder match, else (None, reason).
    """
    if not label:
        return None, "model produced no predicted label"
    if label in identities():
        return label, None
    return None, (
        f"model predicted '{label}', which has no identity folder in "
        f"data/registered/ — no reliable registered match (nothing guessed)"
    )


def sample_photo(identity: str) -> str | None:
    """First supported photo filename for an identity (cached, read-only)."""
    if identity in _photo_cache:
        return _photo_cache[identity]
    found = None
    try:
        for name in sorted(os.listdir(os.path.join(gallery_dir(), identity))):
            full = os.path.join(gallery_dir(), identity, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in SUPPORTED_PHOTO_EXTS:
                found = name
                break
    except OSError:
        found = None
    _photo_cache[identity] = found
    return found


def identity_photos(identity: str | None, limit: int = 10) -> list[dict]:
    """Up to `limit` real gallery photos of an identity.

    Each item: {"filename", "url"}. These are the identity's actual folder
    photos (for visual comparison) — NOT ranked per-photo matches; the
    original CNN index carries no per-row file provenance to rank them by.
    """
    if not identity:
        return []
    out: list[dict] = []
    try:
        names = sorted(os.listdir(os.path.join(gallery_dir(), identity)))
    except OSError:
        return out
    for name in names:
        full = os.path.join(gallery_dir(), identity, name)
        if os.path.isfile(full) and os.path.splitext(name)[1].lower() in SUPPORTED_PHOTO_EXTS:
            out.append({"filename": name,
                        "url": f"/api/dataset/gallery/{identity}/{name}"})
        if len(out) >= limit:
            break
    return out


def gallery_url_for_path(abs_path: str | None) -> str | None:
    """Map an absolute dataset photo path to its gallery URL, or None.

    Used for extension-index rows (API-added photos), which DO know their
    source file — unlike original CNN training rows. Containment-checked:
    anything outside data/registered/ or of unsupported type is rejected.
    """
    if not abs_path:
        return None
    try:
        real = os.path.realpath(abs_path)
        root = os.path.realpath(gallery_dir())
        if os.path.commonpath([real, root]) != root or not os.path.isfile(real):
            return None
        rel = os.path.relpath(real, root).replace("\\", "/")
        parts = rel.split("/")
        if len(parts) != 2:
            return None
        identity, filename = parts
        if os.path.splitext(filename)[1].lower() not in SUPPORTED_PHOTO_EXTS:
            return None
        return f"/api/dataset/gallery/{identity}/{filename}"
    except (OSError, ValueError):
        return None

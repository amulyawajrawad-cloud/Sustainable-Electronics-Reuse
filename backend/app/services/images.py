"""Image upload validation + storage. Files are renamed to random names; type is sniffed
from the file's magic bytes, never trusted from the client's filename or MIME type."""
import os
import uuid
from pathlib import Path

from ..errors import ApiError

MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}


def sniff(head: bytes):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_images(files, cfg) -> list[str]:
    files = [f for f in files if f and f.filename]
    if len(files) > cfg["MAX_IMAGES"]:
        raise ApiError(400, "validation_error", "Too many images.",
                       {"images": f"You can upload at most {cfg['MAX_IMAGES']} images."})
    upload_dir = Path(cfg["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    try:
        for f in files:
            data = f.read(cfg["MAX_IMAGE_BYTES"] + 1)
            if len(data) > cfg["MAX_IMAGE_BYTES"]:
                raise ApiError(400, "validation_error", "Image too large.",
                               {"images": "Each image must be 2 MB or smaller."})
            kind = sniff(data[:16])
            if not kind:
                raise ApiError(400, "validation_error", "Unsupported image.",
                               {"images": "Only PNG, JPEG, GIF or WebP images are allowed."})
            name = f"{uuid.uuid4().hex}.{kind}"
            (upload_dir / name).write_bytes(data)
            saved.append(name)
    except Exception:
        delete_files(saved, cfg)
        raise
    return saved


def delete_files(names, cfg) -> None:
    for n in names:
        try:
            os.remove(Path(cfg["UPLOAD_DIR"]) / n)
        except OSError:
            pass

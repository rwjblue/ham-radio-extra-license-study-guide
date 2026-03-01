from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests


def download_source(url: str, cache_dir: Path | None = None) -> Path:
    extension = _infer_extension(url)
    target: Path
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        target = cache_dir / f"navec-extra-{digest}{extension}"
        if target.exists() and target.stat().st_size > 0:
            return target
    else:
        target = Path(f"pool{extension}")

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def _infer_extension(url: str) -> str:
    path = PurePosixPath(urlparse(url).path)
    suffix = path.suffix.lower()
    if suffix in {".pdf", ".docx"}:
        return suffix
    return ".pdf"

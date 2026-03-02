from __future__ import annotations

import zipfile
from pathlib import Path

from extra_facts.extract import export_docx_media


def test_export_docx_media_exports_word_media_files(tmp_path: Path) -> None:
    docx_path = tmp_path / "pool.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/media/image1.png", b"png-bytes")
        archive.writestr("word/media/image2.jpg", b"jpg-bytes")
        archive.writestr("word/document.xml", b"<w:document/>")

    assets_dir = tmp_path / "assets"
    media_map = export_docx_media(docx_path, assets_dir)

    assert media_map == {
        "word/media/image1.png": "assets/image1.png",
        "word/media/image2.jpg": "assets/image2.jpg",
    }
    assert (assets_dir / "image1.png").read_bytes() == b"png-bytes"
    assert (assets_dir / "image2.jpg").read_bytes() == b"jpg-bytes"

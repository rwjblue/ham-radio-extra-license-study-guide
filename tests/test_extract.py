from __future__ import annotations

from pathlib import Path

from extra_facts.extract import extract_text


def test_extract_text_from_fixture_pdf() -> None:
    pdf_path = Path("tests/fixtures/smoke_pool.pdf")
    text = extract_text(pdf_path)

    assert "E1A01 (A)" in text
    assert "What is the maximum symbol rate?" in text

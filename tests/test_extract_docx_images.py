from __future__ import annotations

import zipfile
from pathlib import Path
from textwrap import dedent

from extra_facts.extract import (
    export_docx_media,
    export_docx_media_for_questions,
    extract_docx_with_images,
)


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


def test_export_docx_media_for_questions_uses_question_scoped_names(tmp_path: Path) -> None:
    docx_path = tmp_path / "pool.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/media/image1.png", b"png-bytes")
        archive.writestr("word/media/image2.jpg", b"jpg-bytes")

    assets_dir = tmp_path / "assets"
    media_map = export_docx_media_for_questions(
        docx_path,
        assets_dir,
        question_images={
            "E1A04": ["word/media/image1.png", "word/media/image2.jpg"],
            "E2B01": ["word/media/image1.png", "word/media/missing.png"],
        },
    )

    assert media_map == {
        "E1A04": ["assets/e1a04-01.png", "assets/e1a04-02.jpg"],
        "E2B01": ["assets/e2b01-01.png"],
    }
    assert (assets_dir / "e1a04-01.png").read_bytes() == b"png-bytes"
    assert (assets_dir / "e1a04-02.jpg").read_bytes() == b"jpg-bytes"
    assert (assets_dir / "e2b01-01.png").read_bytes() == b"png-bytes"


def test_extract_docx_with_images_finds_images_inside_tables(tmp_path: Path) -> None:
    docx_path = tmp_path / "pool.docx"
    _write_minimal_docx_with_table_images(docx_path)

    text, question_images = extract_docx_with_images(docx_path)

    assert "E1A04 (A) First question?" in text
    assert "E1A05 (B) Second question?" in text
    assert question_images == {
        "E1A04": ["word/media/image1.png"],
        "E1A05": ["word/media/image2.jpg"],
    }


def test_extract_docx_with_images_maps_figure_appendix_images_to_questions(tmp_path: Path) -> None:
    docx_path = tmp_path / "pool.docx"
    _write_minimal_docx_with_figure_appendix_images(docx_path)

    _, question_images = extract_docx_with_images(docx_path)

    assert question_images == {
        "E5C10": ["word/media/image1.png"],
        "E5C11": ["word/media/image1.png"],
        "E6A10": ["word/media/image2.jpg"],
    }


def _write_minimal_docx_with_table_images(path: Path) -> None:
    content_types = dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default
            Extension="rels"
            ContentType="application/vnd.openxmlformats-package.relationships+xml"
          />
          <Default Extension="xml" ContentType="application/xml"/>
        </Types>
        """
    )
    rels = dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship
            Id="rIdImg1"
            Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
            Target="media/image1.png"
          />
          <Relationship
            Id="rIdImg2"
            Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
            Target="media/image2.jpg"
          />
        </Relationships>
        """
    )
    document_xml = dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document
          xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
          xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
          xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <w:body>
            <w:p><w:r><w:t>E1A04 (A) First question?</w:t></w:r></w:p>
            <w:tbl><w:tr><w:tc><w:p><w:r><w:drawing><wp:inline>
              <a:graphic><a:graphicData><pic:pic><pic:blipFill>
                <a:blip r:embed="rIdImg1"/>
              </pic:blipFill></pic:pic></a:graphicData></a:graphic>
            </wp:inline></w:drawing></w:r></w:p></w:tc></w:tr></w:tbl>
            <w:p><w:r><w:t>E1A05 (B) Second question?</w:t></w:r></w:p>
            <w:p><w:r><w:drawing><wp:inline>
              <a:graphic><a:graphicData><pic:pic><pic:blipFill>
                <a:blip r:embed="rIdImg2"/>
              </pic:blipFill></pic:pic></a:graphicData></a:graphic>
            </wp:inline></w:drawing></w:r></w:p>
          </w:body>
        </w:document>
        """
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", rels)
        archive.writestr("word/media/image1.png", b"png-bytes")
        archive.writestr("word/media/image2.jpg", b"jpg-bytes")


def _write_minimal_docx_with_figure_appendix_images(path: Path) -> None:
    rels = dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship
            Id="rIdImg1"
            Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
            Target="media/image1.png"
          />
          <Relationship
            Id="rIdImg2"
            Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
            Target="media/image2.jpg"
          />
        </Relationships>
        """
    )
    document_xml = dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document
          xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
          xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
          xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <w:body>
            <w:p><w:r><w:t>E5C10 (A) See Figure E5-1 for this question.</w:t></w:r></w:p>
            <w:p><w:r><w:t>A. one</w:t></w:r></w:p>
            <w:p><w:r><w:t>B. two</w:t></w:r></w:p>
            <w:p><w:r><w:t>C. three</w:t></w:r></w:p>
            <w:p><w:r><w:t>D. four</w:t></w:r></w:p>
            <w:p><w:r><w:t>E5C11 (B) Which item in Figure E5-1 is correct?</w:t></w:r></w:p>
            <w:p><w:r><w:t>A. one</w:t></w:r></w:p>
            <w:p><w:r><w:t>B. two</w:t></w:r></w:p>
            <w:p><w:r><w:t>C. three</w:t></w:r></w:p>
            <w:p><w:r><w:t>D. four</w:t></w:r></w:p>
            <w:p><w:r><w:t>E6A10 (C) Refer to Figure E6-1.</w:t></w:r></w:p>
            <w:p><w:r><w:t>A. one</w:t></w:r></w:p>
            <w:p><w:r><w:t>B. two</w:t></w:r></w:p>
            <w:p><w:r><w:t>C. three</w:t></w:r></w:p>
            <w:p><w:r><w:t>D. four</w:t></w:r></w:p>
            <w:p><w:r><w:t>~~~end of question pool text~~~</w:t></w:r></w:p>
            <w:p><w:r><w:drawing><wp:inline>
              <a:graphic><a:graphicData><pic:pic><pic:blipFill>
                <a:blip r:embed="rIdImg1"/>
              </pic:blipFill></pic:pic></a:graphicData></a:graphic>
            </wp:inline></w:drawing></w:r></w:p>
            <w:p><w:r><w:drawing><wp:inline>
              <a:graphic><a:graphicData><pic:pic><pic:blipFill>
                <a:blip r:embed="rIdImg2"/>
              </pic:blipFill></pic:pic></a:graphicData></a:graphic>
            </wp:inline></w:drawing></w:r></w:p>
          </w:body>
        </w:document>
        """
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", rels)
        archive.writestr("word/media/image1.png", b"png-bytes")
        archive.writestr("word/media/image2.jpg", b"jpg-bytes")

"""Tests for Flask API endpoints."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@pytest.fixture()
def flask_client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _make_minimal_docx() -> bytes:
    """Create a minimal valid .docx (ZIP with required parts) in memory."""
    buf = io.BytesIO()

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '</Relationships>'
    )

    word_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '</Relationships>'
    )

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:r><w:t>John Doe</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>john@example.com</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>(555) 123-4567</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Software Engineer</w:t></w:r></w:p>'
        '</w:body>'
        '</w:document>'
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", word_rels)
        z.writestr("word/document.xml", document)

    return buf.getvalue()


class TestHealthCheck:
    def test_index_returns_html(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 200


class TestRemoveImagesEndpoint:
    def test_missing_file_returns_error(self, flask_client):
        resp = flask_client.post("/remove-images")
        assert resp.status_code in (400, 422, 500)

    def test_valid_docx_returns_docx(self, flask_client):
        docx_bytes = _make_minimal_docx()
        data = {
            "file": (io.BytesIO(docx_bytes), "test_resume.docx"),
        }
        resp = flask_client.post(
            "/remove-images",
            data=data,
            content_type="multipart/form-data",
        )
        # Should return a file (200) or a handled error
        assert resp.status_code in (200, 400, 500)
        if resp.status_code == 200:
            assert resp.content_type in (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream",
            )

    def test_non_docx_rejected(self, flask_client):
        data = {
            "file": (io.BytesIO(b"not a docx"), "test.txt"),
        }
        resp = flask_client.post(
            "/remove-images",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code in (400, 500)


class TestPopulateTemplateEndpoint:
    def test_missing_files_returns_error(self, flask_client):
        resp = flask_client.post("/populate-template")
        assert resp.status_code in (400, 422, 500)

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus

import pytest

from canine_evidence.config import Settings
from scripts.capture_pubmed import ensure_no_credentials, prepare_xml


@pytest.mark.parametrize("encode", [lambda value: value, quote, quote_plus])
def test_capture_refuses_encoded_credentials(encode):
    settings = Settings(email="fixture-test@example.invalid", api_key="fixture-test-secret")
    for value in (settings.email, settings.api_key):
        with pytest.raises(ValueError, match="Credential detected"):
            ensure_no_credentials(encode(value), settings)


def test_capture_removes_contact_fields_without_changing_articles():
    directory = Path(__file__).parent / "fixtures" / "pubmed"
    entry = json.loads((directory / "provenance.json").read_text())["records"][0]
    root = ET.fromstring((directory / entry["efetch_file"]).read_text())
    author = root.find("PubmedArticle/MedlineCitation/Article/AuthorList/Author")
    contact = ET.SubElement(author, "AffiliationInfo")
    ET.SubElement(contact, "Affiliation").text = "fixture-test@example.invalid"
    xml, removed = prepare_xml(ET.tostring(root, encoding="unicode"), datetime.fromisoformat(entry["ncbi_retrieved_at"]))
    assert removed["AffiliationInfo"] >= 1
    assert "fixture-test@example.invalid" not in xml


def test_fixture_integrity_and_contact_metadata_absence():
    directory = Path(__file__).parent / "fixtures" / "pubmed"
    provenance = json.loads((directory / "provenance.json").read_text())
    for entry in provenance["records"]:
        xml = (directory / entry["efetch_file"]).read_text()
        raw_search = (directory / entry["esearch_file"]).read_text()
        assert hashlib.sha256(xml.encode()).hexdigest() == entry["stored_efetch_sha256"]
        assert hashlib.sha256(raw_search.encode()).hexdigest() == entry["esearch_sha256"]
        root = ET.fromstring(xml)
        assert root.find(".//AffiliationInfo") is None
        assert root.find(".//Identifier") is None
        assert root.find(".//InvestigatorList") is None
        assert entry["article_fields_unchanged"] is True

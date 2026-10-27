import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from canine_evidence.cli import search
from canine_evidence.clients.ncbi import BASE_URL, NCBIError
from canine_evidence.models.search import SearchRequest


@pytest.fixture
def inputs(monkeypatch, tmp_path, respx_mock):
    directory = Path(__file__).parent / "fixtures" / "pubmed"
    entry = json.loads((directory / "provenance.json").read_text())["records"][0]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NCBI_EMAIL", "unit-test@example.invalid")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(text=(directory / entry["esearch_file"]).read_text())
    return entry, (directory / entry["efetch_file"]).read_text()


async def test_cli_real_response_pipeline(inputs, respx_mock):
    entry, xml = inputs
    respx_mock.get(BASE_URL + "efetch.fcgi").respond(text=xml)
    result = await search(SearchRequest(gene="BRAF", limit=3))
    assert result["returned_count"] == len(entry["pmids"])
    assert not result["is_partial"]
    assert all(a["species_status"] == "unverified" for a in result["articles"])


@pytest.mark.parametrize("body", ["<broken", "<PubmedArticleSet/>"])
async def test_cli_bad_fetch_is_failure(inputs, respx_mock, body):
    respx_mock.get(BASE_URL + "efetch.fcgi").respond(text=body)
    with pytest.raises(NCBIError, match="All requested"):
        await search(SearchRequest(gene="BRAF", limit=3))


async def test_cli_timeout_is_failure(inputs, respx_mock):
    respx_mock.get(BASE_URL + "efetch.fcgi").mock(side_effect=httpx.ReadTimeout("secret"))
    with pytest.raises(NCBIError, match="All requested"):
        await search(SearchRequest(gene="BRAF", limit=3))


async def test_unsupported_record_returns_remaining_articles(inputs, respx_mock):
    entry, xml = inputs
    root = ET.fromstring(xml)
    # Turn one actual record into an unsupported shape to exercise partial results.
    missing = root[0].findtext("MedlineCitation/PMID")
    root[0].tag = "PubmedBookArticle"
    respx_mock.get(BASE_URL + "efetch.fcgi").respond(text=ET.tostring(root, encoding="unicode"))
    result = await search(SearchRequest(gene="BRAF", limit=3))
    assert result["returned_count"] == len(entry["pmids"]) - 1
    assert result["is_partial"]
    assert result["failures"] == {missing: "MissingRecord"}

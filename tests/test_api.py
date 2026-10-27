import json
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

import httpx
import pytest

from canine_evidence.api import create_app, get_ncbi_client
from canine_evidence.clients.ncbi import BASE_URL
from canine_evidence.config import Settings


@pytest.fixture
async def api_client(monkeypatch):
    monkeypatch.setattr(Settings, "from_env", lambda: Settings("unit-test@example.invalid"))
    app = create_app()
    async with app.router.lifespan_context(app):
        ncbi = app.state.ncbi_client
        ncbi._limiter.acquire = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as http:
            yield app, http, ncbi
    assert ncbi._http.is_closed
    assert not hasattr(app.state, "ncbi_client")


def mock_search(respx_mock, entry):
    return respx_mock.get(BASE_URL + "esearch.fcgi").respond(json={"esearchresult": {
        "count": str(entry["total_count"]), "idlist": entry["pmids"],
        "querytranslation": entry["query_translation"],
    }})


async def test_post_search_real_fixture_pipeline(api_client, respx_mock, pubmed_fixture):
    app, http, ncbi = api_client
    entry, xml, _, _ = pubmed_fixture
    route = mock_search(respx_mock, entry)
    respx_mock.get(BASE_URL + "efetch.fcgi").respond(text=xml)
    for _ in range(2):
        response = await http.post("/search", json={"gene": "BRAF", "species": "dog", "limit": 3})
        assert response.status_code == 200
        body = response.json()
        assert body["total_count"] == entry["total_count"] and body["returned_count"] == 3
        assert body["failed_count"] == 0 and not body["from_cache"]
        assert all(a["species_status"] == "unverified" for a in body["articles"])
        assert app.state.ncbi_client is ncbi
    assert route.call_count == 2


@pytest.mark.parametrize("body", [
    {}, {"gene": " "}, {"gene": "x" * 201}, {"gene": "BRAF", "species": "mouse"},
    {"gene": "BRAF", "year_from": 2020, "year_to": 2010}, {"gene": "BRAF", "limit": 201},
    {"gene": "BRAF", "api_key": "must-not-echo"},
])
async def test_invalid_input_422_without_network(api_client, respx_mock, body):
    response = await api_client[1].post("/search", json=body)
    assert response.status_code == 422 and response.json()["error_type"] == "validation_error"
    assert "must-not-echo" not in response.text
    assert not respx_mock.calls


async def test_empty_search_200(api_client, respx_mock):
    mock_search(respx_mock, {"pmids": [], "total_count": 0, "query_translation": "no-match"})
    response = await api_client[1].post("/search", json={"gene": "BRAF"})
    assert response.status_code == 200 and response.json()["returned_count"] == 0
    assert response.json()["message"] == "설정한 조건에서 검색된 연구 없음"
    assert len(respx_mock.calls) == 1


@pytest.mark.parametrize("upstream,status,kind,attempts", [
    (httpx.ReadTimeout("private"), 503, "timeout", 1),
    (httpx.ConnectError("private"), 503, "network_error", 1),
    (429, 503, "rate_limit", 4), (500, 502, "server_error", 3),
    (400, 502, "upstream_response_error", 1),
])
async def test_esearch_error_mapping(api_client, respx_mock, monkeypatch, upstream, status, kind, attempts):
    monkeypatch.setattr("canine_evidence.clients.ncbi.asyncio.sleep", AsyncMock())
    route = respx_mock.get(BASE_URL + "esearch.fcgi")
    if isinstance(upstream, Exception):
        route.mock(side_effect=upstream)
    else:
        route.respond(upstream)
    response = await api_client[1].post("/search", json={"gene": "BRAF"})
    assert response.status_code == status and response.json()["error_type"] == kind
    assert route.call_count == attempts and "private" not in response.text


@pytest.mark.parametrize("mode,status,reason", [
    ("partial", 200, "NCBITimeoutError"), ("timeout", 503, "NCBITimeoutError"),
    ("429", 503, "NCBIRateLimitError"), ("500", 502, "NCBIServerError"),
    ("parse", 502, "ParseError"), ("missing", 502, "MissingRecord"),
])
async def test_efetch_outcomes(api_client, respx_mock, pubmed_fixture, monkeypatch, mode, status, reason):
    _, http, ncbi = api_client
    entry, xml, _, _ = pubmed_fixture
    mock_search(respx_mock, entry)
    monkeypatch.setattr("canine_evidence.clients.ncbi.asyncio.sleep", AsyncMock())
    if mode == "partial":
        original = ncbi.efetch_batch
        monkeypatch.setattr(ncbi, "efetch_batch", lambda ids: original(ids, batch_size=1))
        first = ET.fromstring(xml)
        for node in list(first)[1:]:
            first.remove(node)
        respx_mock.get(BASE_URL + "efetch.fcgi").mock(side_effect=[
            httpx.Response(200, text=ET.tostring(first, encoding="unicode")),
            httpx.ReadTimeout("private"), httpx.ReadTimeout("private"),
        ])
    elif mode == "timeout":
        respx_mock.get(BASE_URL + "efetch.fcgi").mock(side_effect=httpx.ReadTimeout("private"))
    elif mode in ("429", "500"):
        respx_mock.get(BASE_URL + "efetch.fcgi").respond(int(mode))
    else:
        respx_mock.get(BASE_URL + "efetch.fcgi").respond(text="<broken" if mode == "parse" else "<PubmedArticleSet/>")
    response = await http.post("/search", json={"gene": "BRAF"})
    assert response.status_code == status
    body = response.json()
    assert set(body["failures"].values()) == {reason}
    if mode == "partial":
        assert body["is_partial"] and body["returned_count"] == 1 and body["failed_count"] == 2
    else:
        assert body["error_type"] == "efetch_all_failed" and "articles" not in body


async def test_internal_error_does_not_expose_details(api_client):
    app, http, _ = api_client
    def broken_dependency():
        raise RuntimeError("must-not-expose-internal-secret")
    app.dependency_overrides[get_ncbi_client] = broken_dependency
    response = await http.post("/search", json={"gene": "BRAF"})
    assert response.status_code == 500 and response.json()["error_type"] == "internal_error"
    assert "must-not-expose" not in response.text


async def test_openapi_contract(api_client):
    schema = (await api_client[1].get("/openapi.json")).json()
    assert set(schema["paths"]["/search"]["post"]["responses"]) == {"200", "422", "500", "502", "503"}
    assert "SearchResponse" in schema["components"]["schemas"]

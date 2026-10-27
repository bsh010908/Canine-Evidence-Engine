import json

import pytest

from canine_evidence.cli import search
from canine_evidence.models.search import SearchRequest
from canine_evidence.api import create_app
import httpx


@pytest.mark.live_api
@pytest.mark.parametrize("gene", ["BRAF", "TP53"])
async def test_live_search_and_parse(gene):
    result = await search(SearchRequest(gene=gene, species="dog", limit=3))
    assert result["total_count"] > 0
    assert 1 <= result["returned_count"] <= 3
    assert not result["is_partial"] and not result["failures"]
    for article in result["articles"]:
        assert article["pmid"].isdigit()
        assert article["title"]
        assert article["source_url"] == f'https://pubmed.ncbi.nlm.nih.gov/{article["pmid"]}/'
        assert article["species_status"] == "unverified"
        assert article["ncbi_retrieved_at"]
    # Public metadata only. Credentials and request URLs are never emitted.
    print(json.dumps({"gene": gene, "total_count": result["total_count"],
                      "pmids": [a["pmid"] for a in result["articles"]]}))


@pytest.mark.live_api
@pytest.mark.parametrize("gene", ["BRAF", "TP53"])
async def test_live_fastapi_search(gene):
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/search", json={"gene": gene, "species": "dog", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] >= body["returned_count"] == 3
    assert not body["is_partial"] and body["failed_count"] == 0
    assert all(a["species_status"] == "unverified" for a in body["articles"])
    print(json.dumps({"endpoint": "POST /search", "gene": gene, "total_count": body["total_count"],
                      "pmids": [a["pmid"] for a in body["articles"]]}))

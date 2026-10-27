import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from canine_evidence.clients.ncbi import (
    BASE_URL, NCBIClient, NCBINetworkError, NCBIRateLimitError,
    NCBIResponseError, NCBIServerError, NCBITimeoutError, RateLimiter,
)


@pytest.fixture
async def client():
    async with NCBIClient("unit-test@example.invalid", "unit-test-key") as client:
        client._limiter.acquire = AsyncMock()
        yield client


@pytest.fixture
def sleep(monkeypatch):
    mocked = AsyncMock()
    monkeypatch.setattr("canine_evidence.clients.ncbi.asyncio.sleep", mocked)
    return mocked


async def test_empty_search(client, respx_mock):
    route = respx_mock.get(BASE_URL + "esearch.fcgi").respond(json={"esearchresult": {
        "count": "0", "idlist": [], "querytranslation": "no-match",
        "warninglist": {"outputmessages": ["No items found."]},
    }})
    result = await client.esearch("no-match")
    assert result.total_count == 0 and result.pmids == []
    assert result.warnings
    params = route.calls[0].request.url.params
    assert params["api_key"] == "unit-test-key" and "apiKey" not in params
    assert params["retmode"] == "json" and params["db"] == "pubmed"


async def test_http_logs_redact_credentials(client, respx_mock, caplog):
    caplog.set_level(logging.DEBUG)
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(json={"esearchresult": {
        "count": "0", "idlist": [], "querytranslation": "no-match",
    }})
    await client.esearch("no-match")
    assert "[REDACTED]" in caplog.text
    assert "unit-test-key" not in caplog.text
    assert "unit-test%40example.invalid" not in caplog.text
    assert "unit-test@example.invalid" not in caplog.text


@pytest.mark.parametrize("payload", [
    {}, [], {"esearchresult": []}, {"error": "upstream error"}, {"esearchresult": {"errorlist": {"fieldnotfound": ["bad"]}}},
    {"esearchresult": {"count": "1", "idlist": [], "querytranslation": "x"}},
    {"esearchresult": {"count": "0", "idlist": ["bad"], "querytranslation": "x"}},
])
async def test_invalid_json_contract(client, respx_mock, payload):
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(json=payload)
    with pytest.raises(NCBIResponseError):
        await client.esearch("BRAF")


async def test_html_is_not_empty_result(client, respx_mock):
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(text="<html>upstream unavailable</html>")
    with pytest.raises(NCBIResponseError):
        await client.esearch("BRAF")


@pytest.mark.parametrize("status,error,delays", [
    (429, NCBIRateLimitError, [1, 2, 4]), (500, NCBIServerError, [1, 2]),
])
async def test_retry_exhaustion(client, respx_mock, sleep, status, error, delays):
    route = respx_mock.get(BASE_URL + "esearch.fcgi").respond(status, text="upstream error")
    with pytest.raises(error):
        await client.esearch("BRAF")
    assert route.call_count == len(delays) + 1
    assert [call.args[0] for call in sleep.call_args_list] == delays
    assert client._limiter.acquire.await_count == route.call_count


async def test_retry_after(client, respx_mock, sleep):
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(429, headers={"Retry-After": "5"})
    with pytest.raises(NCBIRateLimitError):
        await client.esearch("BRAF")
    assert [call.args[0] for call in sleep.call_args_list] == [5, 5, 5]


@pytest.mark.parametrize("exception,error", [
    (httpx.ReadTimeout("secret URL"), NCBITimeoutError),
    (httpx.ConnectError("secret URL"), NCBINetworkError),
])
async def test_transport_failure_sanitized(client, respx_mock, exception, error):
    route = respx_mock.get(BASE_URL + "esearch.fcgi").mock(side_effect=exception)
    with pytest.raises(error) as caught:
        await client.esearch("BRAF")
    assert "secret" not in str(caught.value) and route.call_count == 1


async def test_http_400_not_retried(client, respx_mock):
    route = respx_mock.get(BASE_URL + "esearch.fcgi").respond(400)
    with pytest.raises(NCBIResponseError):
        await client.esearch("BRAF")
    assert route.call_count == 1


@pytest.mark.parametrize("rate", [3, 10])
async def test_concurrent_rate_limit(monkeypatch, rate):
    clock = [0.0]
    starts = []
    monkeypatch.setattr("canine_evidence.clients.ncbi.time.monotonic", lambda: clock[0])

    async def advance(delay):
        clock[0] += delay

    monkeypatch.setattr("canine_evidence.clients.ncbi.asyncio.sleep", advance)
    limiter = RateLimiter(rate)

    async def request():
        await limiter.acquire()
        starts.append(clock[0])

    await asyncio.gather(*(request() for _ in range(2 * rate)))
    assert all(b - a >= 1 / rate for a, b in zip(starts, starts[1:]))
    assert all(sum(t <= s < t + 1 for s in starts) <= rate for t in starts)


async def test_no_ids_no_fetch(client, respx_mock):
    result = await client.efetch_batch([])
    assert result.batches == [] and result.failed_pmids == []
    assert not respx_mock.calls


@pytest.fixture
def captured():
    directory = Path(__file__).parent / "fixtures" / "pubmed"
    entry = json.loads((directory / "provenance.json").read_text())["records"][0]
    return entry, (directory / entry["esearch_file"]).read_text(), (directory / entry["efetch_file"]).read_text()


async def test_real_search_response(client, respx_mock, captured):
    entry, search_json, _ = captured
    respx_mock.get(BASE_URL + "esearch.fcgi").respond(text=search_json)
    found = await client.esearch(entry["query"], retmax=3)
    assert found.pmids == entry["pmids"] and found.total_count == entry["total_count"]


async def test_fetch_partial_retains_failure_causes(client, respx_mock, sleep, captured):
    entry, _, xml = captured
    ids = entry["pmids"][:2]
    route = respx_mock.get(BASE_URL + "efetch.fcgi").mock(side_effect=[
        httpx.Response(200, text=xml), httpx.Response(503), httpx.Response(503), httpx.Response(503),
    ])
    result = await client.efetch_batch(ids, batch_size=1)
    assert len(result.batches) == 1 and result.batches[0].pmids == ids[:1]
    assert result.batches[0].xml == xml
    assert result.failures == {ids[1]: "NCBIServerError"}
    assert route.call_count == 4


async def test_all_fetch_failures_not_empty_success(client, respx_mock, captured):
    entry, _, _ = captured
    respx_mock.get(BASE_URL + "efetch.fcgi").mock(side_effect=httpx.ReadTimeout("secret"))
    result = await client.efetch_batch(entry["pmids"])
    assert not result.batches
    assert result.failures == dict.fromkeys(entry["pmids"], "NCBITimeoutError")


async def test_recovery_after_429(client, respx_mock, sleep, captured):
    entry, search_json, _ = captured
    route = respx_mock.get(BASE_URL + "esearch.fcgi").mock(side_effect=[
        httpx.Response(429), httpx.Response(200, text=search_json),
    ])
    assert (await client.esearch(entry["query"])).pmids == entry["pmids"]
    assert route.call_count == 2

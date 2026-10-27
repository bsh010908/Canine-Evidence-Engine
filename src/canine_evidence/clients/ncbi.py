"""NCBI E-utilities client. Share one instance across concurrent requests."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def _redact_request_credentials(record: logging.LogRecord) -> bool:
    """Keep HTTP diagnostics usable without logging query credentials."""
    record.msg = re.sub(
        r'''(?i)(email|api_key)=[^&\s"'\\]+''',
        r"\1=[REDACTED]", record.getMessage(),
    )
    record.args = ()
    return True


class NCBIError(Exception):
    """Sanitized upstream failure; never contains a credential-bearing URL."""


class NCBITimeoutError(NCBIError):
    pass


class NCBIRateLimitError(NCBIError):
    pass


class NCBIServerError(NCBIError):
    pass


class NCBINetworkError(NCBIError):
    pass


class NCBIResponseError(NCBIError):
    pass


class RateLimiter:
    """Serialize request starts with spacing, including retries (no burst)."""

    def __init__(self, rate: int) -> None:
        self.interval = 1 / rate + 0.001
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            delay = self._next - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next = time.monotonic() + self.interval


@dataclass
class ESearchResult:
    pmids: list[str]
    total_count: int
    query_translation: str
    warnings: dict
    raw_json: str
    retrieved_at: datetime


@dataclass
class FetchedBatch:
    pmids: list[str]
    xml: str
    retrieved_at: datetime


@dataclass
class EFetchBatchResult:
    batches: list[FetchedBatch] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def failed_pmids(self) -> list[str]:
        return list(self.failures)


class NCBIClient:
    def __init__(self, email: str, api_key: str | None = None, *, timeout: float = 30.0) -> None:
        if not email.strip() or "@" not in email:
            raise ValueError("A contact email is required")
        self._params = {"tool": "canine-evidence-engine", "email": email}
        if api_key:
            self._params["api_key"] = api_key
        self._http = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)
        for name in tuple(logging.Logger.manager.loggerDict):
            if name == "httpx" or name.startswith("httpcore."):
                logging.getLogger(name).addFilter(_redact_request_credentials)
        self._limiter = RateLimiter(10 if api_key else 3)

    async def __aenter__(self) -> "NCBIClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._http.aclose()

    async def _get(self, endpoint: str, params: dict) -> httpx.Response:
        rate_retries = server_retries = 0
        while True:
            await self._limiter.acquire()
            try:
                response = await self._http.get(endpoint, params={**self._params, **params})
            except httpx.TimeoutException:
                raise NCBITimeoutError("NCBI request timed out") from None
            except httpx.RequestError:
                raise NCBINetworkError("NCBI network request failed") from None
            if response.status_code == 429:
                if rate_retries == 3:
                    raise NCBIRateLimitError("NCBI rate-limit retries exhausted")
                delay = 2 ** rate_retries
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
                await asyncio.sleep(delay)
                rate_retries += 1
            elif response.status_code >= 500:
                if server_retries == 2:
                    raise NCBIServerError("NCBI server retries exhausted")
                await asyncio.sleep(2 ** server_retries)
                server_retries += 1
            elif response.status_code != 200:
                raise NCBIResponseError(f"NCBI returned HTTP {response.status_code}")
            else:
                return response

    async def esearch(self, query: str, retmax: int = 20) -> ESearchResult:
        if not 1 <= retmax <= 200:
            raise ValueError("retmax must be between 1 and 200")
        response = await self._get("esearch.fcgi", {
            "db": "pubmed", "term": query, "retmax": retmax,
            "retmode": "json", "sort": "pub_date",
        })
        retrieved_at = datetime.now(timezone.utc)
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid response object")
            result = payload["esearchresult"]
            if not isinstance(result, dict):
                raise ValueError("invalid search object")
            if payload.get("error") or result.get("ERROR") or result.get("errorlist"):
                raise ValueError("upstream error")
            pmids = result["idlist"]
            count = int(result["count"])
            translation = result["querytranslation"]
            warnings = result.get("warninglist", {})
            if (not isinstance(pmids, list) or len(pmids) > retmax or count < len(pmids)
                    or count < 0 or not isinstance(translation, str) or not isinstance(warnings, dict)
                    or any(not isinstance(p, str) or not re.fullmatch(r"[1-9][0-9]*", p) for p in pmids)
                    or (count > 0 and not pmids)):
                raise ValueError("invalid search result")
        except (ValueError, TypeError, KeyError):
            raise NCBIResponseError("Invalid or error-bearing NCBI ESearch response") from None
        return ESearchResult(pmids, count, translation, warnings, response.text, retrieved_at)

    async def efetch_batch(self, pmids: list[str], batch_size: int = 100) -> EFetchBatchResult:
        if not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        if any(not re.fullmatch(r"[1-9][0-9]*", p) for p in pmids):
            raise ValueError("Invalid PMID")
        result = EFetchBatchResult()
        for offset in range(0, len(pmids), batch_size):
            batch = pmids[offset:offset + batch_size]
            try:
                response = await self._get("efetch.fcgi", {
                    "db": "pubmed", "id": ",".join(batch), "retmode": "xml",
                })
            except NCBIError as exc:
                result.failures.update({pmid: type(exc).__name__ for pmid in batch})
            else:
                result.batches.append(FetchedBatch(batch, response.text, datetime.now(timezone.utc)))
        return result

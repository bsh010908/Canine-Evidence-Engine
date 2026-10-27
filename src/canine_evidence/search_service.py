"""SearchService responsibility implemented as a function with an owned client supplied."""

import logging
from datetime import datetime, timezone

from canine_evidence.clients.ncbi import NCBIClient, NCBIError
from canine_evidence.deduplication import deduplicate
from canine_evidence.models.article import Article
from canine_evidence.models.search import SearchRequest, SearchResponse
from canine_evidence.parsers.pubmed_xml import ParseError, parse_efetch_xml
from canine_evidence.query_builder import build_query

logger = logging.getLogger(__name__)
TRANSIENT_FAILURES = {"NCBITimeoutError", "NCBINetworkError", "NCBIRateLimitError"}


class EFetchAllFailed(NCBIError):
    def __init__(self, failures: dict[str, str]) -> None:
        super().__init__("All requested EFetch records failed or were missing")
        self.failures = failures


async def search(request: SearchRequest, client: NCBIClient) -> SearchResponse:
    searched_at = datetime.now(timezone.utc)
    query = build_query(request)
    found = await client.esearch(query, retmax=request.limit)
    articles: list[Article] = []
    failures: dict[str, str] = {}
    if found.pmids:
        fetched = await client.efetch_batch(found.pmids)
        failures.update(fetched.failures)
        for batch in fetched.batches:
            try:
                parsed = parse_efetch_xml(batch.xml, retrieved_at=batch.retrieved_at)
            except ParseError:
                failures.update({pmid: "ParseError" for pmid in batch.pmids})
                continue
            expected = set(batch.pmids)
            # Never attach an unrequested PMID to this search, even in mixed XML.
            accepted = [article for article in parsed if article.pmid in expected]
            if len(accepted) != len(parsed):
                logger.warning("Excluded unexpected PMIDs from EFetch batch")
            articles.extend(accepted)
            received = {article.pmid for article in accepted}
            failures.update({pmid: "MissingRecord" for pmid in batch.pmids if pmid not in received})
        articles = deduplicate(articles)
        received = {article.pmid for article in articles}
        # Preserve ESearch order and handle any omitted client batch defensively.
        failures = {pmid: failures.get(pmid, "MissingRecord")
                    for pmid in dict.fromkeys(found.pmids) if pmid not in received}
        for pmid, reason in failures.items():
            logger.warning("EFetch failed PMID %s: %s", pmid, reason)
        if not articles:
            raise EFetchAllFailed(failures)
    # Stable sort preserves first-record selection and input order for equal years.
    articles.sort(key=lambda article: article.publication_year or 0, reverse=True)
    return SearchResponse(
        articles=articles, total_count=found.total_count, returned_count=len(articles),
        searched_at=searched_at, query_string=query, query_translation=found.query_translation,
        esearch_retrieved_at=found.retrieved_at, warnings=found.warnings,
        is_partial=bool(failures), failures=failures, failed_pmids=list(failures),
        failed_count=len(failures),
        message="설정한 조건에서 검색된 연구 없음" if found.total_count == 0 else None,
    )

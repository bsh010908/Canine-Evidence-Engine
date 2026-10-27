"""Stable PMID deduplication; DOI collisions never discard papers."""

import logging
from collections.abc import Iterable

from canine_evidence.models.article import Article

logger = logging.getLogger(__name__)


def deduplicate(articles: Iterable[Article]) -> list[Article]:
    result: list[Article] = []
    seen_pmids: set[str] = set()
    doi_owners: dict[str, str] = {}
    for article in articles:
        if not article.pmid:
            logger.warning("Excluded article without PMID")
            continue
        if article.pmid in seen_pmids:
            continue
        seen_pmids.add(article.pmid)
        if article.doi is not None:
            owner = doi_owners.setdefault(article.doi, article.pmid)
            if owner != article.pmid:
                logger.warning("DOI collision between PMIDs %s and %s; keeping both", owner, article.pmid)
        result.append(article)
    return result

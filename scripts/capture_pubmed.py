"""Capture real responses with contact metadata removed and provenance recorded.

Run: python scripts/capture_pubmed.py --output tests/fixtures/pubmed
"""

import argparse
import asyncio
import json
import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, quote_plus
from datetime import datetime
from pathlib import Path

from canine_evidence.clients.ncbi import BASE_URL, NCBIClient
from canine_evidence.config import Settings
from canine_evidence.models.search import SearchRequest
from canine_evidence.parsers.pubmed_xml import parse_efetch_xml
from canine_evidence.query_builder import build_query


def ensure_no_credentials(text: str, settings: Settings) -> None:
    for secret in (settings.email, settings.api_key):
        if secret and any(value in text for value in (secret, quote(secret, safe=""), quote_plus(secret))):
            raise ValueError("Credential detected; persistence refused")


def prepare_xml(xml: str, retrieved_at: datetime) -> tuple[str, dict[str, int]]:
    original_articles = parse_efetch_xml(xml, retrieved_at=retrieved_at)
    root = ET.fromstring(xml)
    removed: dict[str, int] = {}
    # Contact details and personal identifiers are not needed for parser tests.
    for parent in root.iter():
        for child in list(parent):
            if child.tag in {"AffiliationInfo", "Identifier", "InvestigatorList"}:
                removed[child.tag] = removed.get(child.tag, 0) + 1
                parent.remove(child)
    sanitized = ET.tostring(root, encoding="unicode")
    if re.search(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sanitized):
        raise ValueError("Contact address remains in XML; manual review required")
    if parse_efetch_xml(sanitized, retrieved_at=retrieved_at) != original_articles:
        raise ValueError("Sanitization changed article fields; capture refused")
    return sanitized, removed


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def capture(output: Path) -> None:
    settings = Settings.from_env()
    manifest = {"source": BASE_URL, "records": []}
    files: dict[str, str] = {}
    async with NCBIClient(settings.email, settings.api_key) as client:
        for gene in ("BRAF", "TP53"):
            query = build_query(SearchRequest(gene=gene, species="dog", limit=3))
            search = await client.esearch(query, retmax=3)
            if not search.pmids:
                raise RuntimeError(f"No records returned for {gene}")
            fetched = await client.efetch_batch(search.pmids)
            if fetched.failures:
                raise RuntimeError(f"EFetch failed: {fetched.failures}")
            batch = fetched.batches[0]
            articles = parse_efetch_xml(batch.xml, retrieved_at=batch.retrieved_at)
            if {article.pmid for article in articles} != set(search.pmids):
                raise RuntimeError("ESearch/EFetch PMID mismatch; capture refused")
            sanitized, removed = prepare_xml(batch.xml, batch.retrieved_at)
            ensure_no_credentials(search.raw_json + sanitized, settings)
            search_name = f"{gene.lower()}_esearch.json"
            xml_name = f"{gene.lower()}_efetch.xml"
            files[search_name] = search.raw_json
            files[xml_name] = sanitized
            manifest["records"].append({
                "gene": gene, "query": query, "pmids": search.pmids,
                "total_count": search.total_count,
                "query_translation": search.query_translation, "warnings": search.warnings,
                "esearch_retrieved_at": search.retrieved_at.isoformat(),
                "ncbi_retrieved_at": batch.retrieved_at.isoformat(),
                "esearch_file": search_name, "efetch_file": xml_name,
                "raw_efetch_sha256": sha256(batch.xml),
                "stored_efetch_sha256": sha256(sanitized),
                "esearch_sha256": sha256(search.raw_json),
                "removed_contact_metadata": removed,
                "article_fields_unchanged": True,
            })
    # Both searches, privacy checks and PMID checks must finish before writing.
    files["provenance.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    for content in files.values():
        ensure_no_credentials(content, settings)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (output / name).write_text(content, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(capture(parser.parse_args().output))

import copy
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from canine_evidence.clients.ncbi import ESearchResult, EFetchBatchResult, FetchedBatch
from canine_evidence.models.search import SearchRequest, SearchResponse
from canine_evidence.search_service import EFetchAllFailed, search


@pytest.fixture
def service_client(pubmed_fixture):
    entry, xml, timestamp, _ = pubmed_fixture
    return SimpleNamespace(
        esearch=AsyncMock(return_value=ESearchResult(entry["pmids"], entry["total_count"], entry["query_translation"], {}, "", timestamp)),
        efetch_batch=AsyncMock(return_value=EFetchBatchResult([FetchedBatch(entry["pmids"], xml, timestamp)])),
    )


async def test_service_counts_times_and_unverified(service_client, pubmed_fixture):
    before = datetime.now(timezone.utc)
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert result.total_count == pubmed_fixture[0]["total_count"]
    assert result.returned_count == 3
    assert result.searched_at >= before
    assert result.esearch_retrieved_at == pubmed_fixture[2]
    assert all(a.ncbi_retrieved_at == pubmed_fixture[2] and a.species_status == "unverified" for a in result.articles)
    assert SearchResponse.model_validate_json(result.model_dump_json()) == result


async def test_empty_does_not_call_efetch(service_client):
    found = service_client.esearch.return_value
    found.pmids, found.total_count = [], 0
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert result.articles == [] and result.returned_count == result.total_count == 0
    assert result.message == "설정한 조건에서 검색된 연구 없음"
    assert not result.is_partial
    service_client.efetch_batch.assert_not_awaited()


async def test_duplicates_first_record_kept(service_client, pubmed_fixture):
    root = ET.fromstring(pubmed_fixture[1])
    later = copy.deepcopy(root[0])
    later.find("MedlineCitation/Article").remove(later.find("MedlineCitation/Article/ArticleTitle"))
    root.append(later)
    service_client.efetch_batch.return_value.batches[0].xml = ET.tostring(root, encoding="unicode")
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert result.returned_count == 3
    assert result.articles[0].title == pubmed_fixture[3][0].title
    assert not result.is_partial


async def test_partial_parse_failure_preserves_other_batch(service_client, pubmed_fixture):
    entry, xml, timestamp, _ = pubmed_fixture
    root = ET.fromstring(xml)
    root.remove(root[-1])
    service_client.efetch_batch.return_value = EFetchBatchResult([
        FetchedBatch(entry["pmids"][:2], ET.tostring(root, encoding="unicode"), timestamp),
        FetchedBatch(entry["pmids"][2:], "<broken", timestamp),
    ])
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert result.returned_count == 2 and result.is_partial
    assert result.failures == {entry["pmids"][2]: "ParseError"}
    assert result.failed_count == 1


async def test_unexpected_ids_excluded_without_losing_valid(service_client, pubmed_fixture):
    service_client.esearch.return_value.pmids = pubmed_fixture[0]["pmids"][:2]
    service_client.efetch_batch.return_value.batches[0].pmids = pubmed_fixture[0]["pmids"][:2]
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert {a.pmid for a in result.articles} == set(pubmed_fixture[0]["pmids"][:2])


async def test_all_missing_is_not_empty_success(service_client, pubmed_fixture):
    service_client.efetch_batch.return_value.batches[0].xml = "<PubmedArticleSet/>"
    with pytest.raises(EFetchAllFailed) as exc:
        await search(SearchRequest(gene="BRAF"), service_client)
    assert exc.value.failures == dict.fromkeys(pubmed_fixture[0]["pmids"], "MissingRecord")


async def test_sort_year_descending_null_last(service_client, pubmed_fixture):
    root = ET.fromstring(pubmed_fixture[1])
    for record, year in zip(root, (None, "2023", "2025")):
        date = record.find("MedlineCitation/Article/Journal/JournalIssue/PubDate")
        date.remove(date.find("Year"))
        if year:
            ET.SubElement(date, "Year").text = year
    service_client.efetch_batch.return_value.batches[0].xml = ET.tostring(root, encoding="unicode")
    result = await search(SearchRequest(gene="BRAF"), service_client)
    assert [a.publication_year for a in result.articles] == [2025, 2023, None]


@pytest.mark.parametrize("change", [
    {"returned_count": 0}, {"total_count": 0}, {"is_partial": True}, {"failed_count": 1},
])
async def test_response_invariants(service_client, change):
    result = await search(SearchRequest(gene="BRAF"), service_client)
    with pytest.raises(ValidationError):
        SearchResponse.model_validate(result.model_dump() | change)

import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pytest

from canine_evidence.models.article import Article
from canine_evidence.parsers.pubmed_xml import ParseError, parse_efetch_xml

FIXTURES = Path(__file__).parent / "fixtures" / "pubmed"


@pytest.fixture
def source_record():
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    entry = provenance["records"][0]
    xml = (FIXTURES / entry["efetch_file"]).read_text()
    return ET.fromstring(xml), datetime.fromisoformat(entry["ncbi_retrieved_at"])


@pytest.mark.parametrize("gene", ["braf", "tp53"])
def test_real_xml_mapping(gene):
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    entry = next(record for record in provenance["records"] if record["gene"].lower() == gene)
    xml = (FIXTURES / entry["efetch_file"]).read_text()
    timestamp = datetime.fromisoformat(entry["ncbi_retrieved_at"])
    assert hashlib.sha256(xml.encode()).hexdigest() == entry["stored_efetch_sha256"]
    articles = parse_efetch_xml(xml, retrieved_at=timestamp)
    assert {a.pmid for a in articles} == set(entry["pmids"])
    root = ET.fromstring(xml)
    for article, record in zip(articles, root.findall("PubmedArticle"), strict=True):
        citation = record.find("MedlineCitation")
        source = citation.find("Article")
        assert article.pmid == citation.findtext("PMID")
        assert article.title == "".join(source.find("ArticleTitle").itertext()).strip()
        assert article.doi == record.findtext('PubmedData/ArticleIdList/ArticleId[@IdType="doi"]')
        assert article.journal == source.findtext("Journal/Title")
        assert article.ncbi_retrieved_at == timestamp
        assert article.source_url == f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/"
        assert article.species_status == "unverified"
        assert article.species_evidence_notes == []
        assert article.mesh_terms == [n.text for n in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")]
        assert article.publication_types == [n.text for n in source.findall("PublicationTypeList/PublicationType")]
        expected_year = source.findtext("Journal/JournalIssue/PubDate/Year")
        assert article.publication_year == (int(expected_year) if expected_year else None)
        expected_sections = []
        for node in source.findall("Abstract/AbstractText"):
            content = "".join(node.itertext()).strip()
            if content:
                expected_sections.append(f'{node.get("Label")}: {content}' if node.get("Label") else content)
        assert article.abstract == ("\n".join(expected_sections) or None)
        assert article.abstract_available == bool(expected_sections)
        expected_authors = []
        for author in source.findall("AuthorList/Author"):
            collective = author.findtext("CollectiveName")
            expected_authors.append(collective or " ".join(filter(None, [
                author.findtext("LastName"), author.findtext("ForeName") or author.findtext("Initials"),
                author.findtext("Suffix"),
            ])))
        assert article.authors == expected_authors
        assert Article.model_validate_json(article.model_dump_json()) == article


def test_missing_optional_fields(source_record):
    root, timestamp = source_record
    record = root[0]
    citation = record.find("MedlineCitation")
    source = citation.find("Article")
    # Fault injection only: delete real fields; no fictitious paper is created.
    for parent, tag in [(source, "Abstract"), (source, "ArticleTitle"), (source, "AuthorList"),
                        (source, "Journal"), (source, "PublicationTypeList"),
                        (citation, "MeshHeadingList"), (record, "PubmedData")]:
        for child in parent.findall(tag):
            parent.remove(child)
    article = parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)[0]
    assert article.abstract is None and not article.abstract_available
    assert article.doi is None and article.title is None and article.publication_year is None
    assert article.authors == [] and article.mesh_terms == [] and article.publication_types == []
    assert article.journal is None


def test_missing_pmid_excluded(source_record, caplog):
    root, timestamp = source_record
    citation = root[0].find("MedlineCitation")
    removed = citation.findtext("PMID")
    citation.remove(citation.find("PMID"))
    articles = parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)
    assert removed not in [a.pmid for a in articles]
    assert "Excluded 1 NCBI records" in caplog.text


def test_no_year_inference(source_record):
    root, timestamp = source_record
    source = root[0].find("MedlineCitation/Article")
    date = source.find("Journal/JournalIssue/PubDate")
    for year in date.findall("Year"):
        date.remove(year)
    article = parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)[0]
    assert article.publication_year is None


def test_missing_required_structure(source_record):
    root, timestamp = source_record
    root[0].remove(root[0].find("MedlineCitation"))
    with pytest.raises(ParseError, match="MedlineCitation"):
        parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)


def test_unsupported_record_preserves_normal_articles(source_record, caplog):
    root, timestamp = source_record
    expected = parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)
    # Structural fault injection: not a fabricated publication or PMID.
    root.insert(0, ET.Element("PubmedBookArticle"))
    root.append(ET.Element("UnsupportedRecord"))
    actual = parse_efetch_xml(ET.tostring(root, encoding="unicode"), retrieved_at=timestamp)
    assert actual == expected
    assert "Excluded 2 unsupported NCBI records" in caplog.text


@pytest.mark.parametrize("xml", [
    "<broken", "<html/>", "<eFetchResult><ERROR>failure</ERROR></eFetchResult>",
    "<PubmedArticleSet><ERROR>failure</ERROR></PubmedArticleSet>",
    '<!DOCTYPE x [<!ENTITY x "x">]><PubmedArticleSet/>',
    "<PubmedArticleSet><PubmedBookArticle/></PubmedArticleSet>",
])
def test_bad_xml_not_empty_success(xml):
    with pytest.raises(ParseError):
        parse_efetch_xml(xml, retrieved_at=datetime.now(timezone.utc))


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_efetch_xml("<PubmedArticleSet/>", retrieved_at=datetime(2026, 1, 1))

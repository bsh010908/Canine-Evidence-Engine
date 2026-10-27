import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from canine_evidence.models.article import Article

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    """Malformed or unsupported upstream structure."""


def _text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    return "".join(node.itertext()).strip() or None


def parse_efetch_xml(xml_text: str, *, retrieved_at: datetime) -> list[Article]:
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    # PubMed's normal external DTD declaration is accepted, but entities
    # are never expanded from custom declarations or external resources.
    if re.search(r"<!ENTITY\s", xml_text, re.IGNORECASE):
        raise ParseError("XML entity declarations are not accepted")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise ParseError("Invalid NCBI XML") from None
    if root.tag != "PubmedArticleSet" or root.find(".//ERROR") is not None:
        raise ParseError("Missing PubmedArticleSet or upstream XML error")
    unsupported_count = sum(child.tag != "PubmedArticle" for child in root)
    if unsupported_count:
        logger.warning("Excluded %d unsupported NCBI records", unsupported_count)
        if not root.findall("PubmedArticle"):
            raise ParseError("No supported records in PubmedArticleSet")
    articles: list[Article] = []
    excluded = 0
    for record in root.findall("PubmedArticle"):
        citation = record.find("MedlineCitation")
        if citation is None:
            raise ParseError("Missing MedlineCitation")
        pmid = _text(citation.find("PMID"))
        if pmid is None or not re.fullmatch(r"[1-9][0-9]*", pmid):
            excluded += 1
            continue
        source = citation.find("Article")
        if source is None:
            raise ParseError("Missing Article structure")
        sections = []
        for section in source.findall("Abstract/AbstractText"):
            text = _text(section)
            if text:
                label = section.get("Label")
                sections.append(f"{label}: {text}" if label else text)
        abstract = "\n".join(sections) or None
        authors = []
        for author in source.findall("AuthorList/Author"):
            collective = _text(author.find("CollectiveName"))
            name = collective or " ".join(filter(None, [
                _text(author.find("LastName")),
                _text(author.find("ForeName")) or _text(author.find("Initials")),
                _text(author.find("Suffix")),
            ]))
            if name:
                authors.append(name)
        year_text = _text(source.find("Journal/JournalIssue/PubDate/Year"))
        year = int(year_text) if year_text and re.fullmatch(r"[0-9]{4}", year_text) else None
        articles.append(Article(
            pmid=pmid,
            doi=_text(record.find('PubmedData/ArticleIdList/ArticleId[@IdType="doi"]')),
            title=_text(source.find("ArticleTitle")), abstract=abstract,
            abstract_available=abstract is not None, authors=authors,
            publication_year=year, journal=_text(source.find("Journal/Title")),
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            ncbi_retrieved_at=retrieved_at.astimezone(timezone.utc),
            mesh_terms=[text for node in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")
                        if (text := _text(node))],
            publication_types=[text for node in source.findall("PublicationTypeList/PublicationType")
                               if (text := _text(node))],
        ))
    if excluded:
        logger.warning("Excluded %d NCBI records: missing or invalid PMID", excluded)
    return articles

from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class Article(BaseModel):
    # Records without a valid source PMID are rejected before model creation.
    pmid: str = Field(pattern=r"^[1-9][0-9]*$")
    doi: str | None = None
    title: str | None = None
    abstract: str | None = None
    abstract_available: bool
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    journal: str | None = None
    source_url: str
    ncbi_retrieved_at: AwareDatetime
    mesh_terms: list[str] = Field(default_factory=list)
    # Author-supplied keywords (KeywordList Owner="NOTNLM"); PubMed [tiab] also searches them.
    keywords: list[str] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list)
    species_status: Literal["unverified"] = "unverified"
    species_evidence_strength: Literal["low"] = "low"
    species_evidence_notes: list[str] = Field(default_factory=list)

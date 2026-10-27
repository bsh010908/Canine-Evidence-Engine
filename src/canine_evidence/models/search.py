import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from canine_evidence.models.article import Article


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gene: str = Field(min_length=1, max_length=200)
    species: Literal["dog", "cat", "human", "all"] = "all"
    year_from: int | None = None
    year_to: int | None = None
    cancer_keyword: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=20, ge=1, le=200)

    @field_validator("gene", mode="before")
    @classmethod
    def validate_gene(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("gene must be a string")
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9/ -]+", value) or not re.search(r"[A-Za-z0-9]", value):
            raise ValueError("gene permits letters, numbers, spaces, hyphens and slashes only")
        return value

    @field_validator("cancer_keyword", mode="before")
    @classmethod
    def validate_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("cancer_keyword must be a string")
        value = value.strip()
        if any(not (c.isalnum() or c in " -/") for c in value):
            raise ValueError("cancer_keyword contains unsupported search syntax")
        return value or None

    @field_validator("year_from", "year_to")
    @classmethod
    def validate_year(cls, value: int | None) -> int | None:
        if value is not None and not 1800 <= value <= datetime.now(timezone.utc).year:
            raise ValueError("year must be between 1800 and the current UTC year")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "SearchRequest":
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from must not exceed year_to")
        return self


class SearchResponse(BaseModel):
    articles: list[Article]
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=200)
    searched_at: AwareDatetime
    query_string: str
    query_translation: str
    esearch_retrieved_at: AwareDatetime
    is_partial: bool = False
    failed_pmids: list[str] = Field(default_factory=list)
    failed_count: int = Field(default=0, ge=0)
    failures: dict[str, str] = Field(default_factory=dict)
    warnings: dict[str, list[str]] = Field(default_factory=dict)
    from_cache: Literal[False] = False
    message: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "SearchResponse":
        ids = [article.pmid for article in self.articles]
        if len(ids) != len(set(ids)) or self.returned_count != len(ids):
            raise ValueError("returned_count must match unique articles")
        if self.total_count < self.returned_count:
            raise ValueError("total_count cannot be less than returned_count")
        if self.failed_pmids != list(self.failures) or self.failed_count != len(self.failures):
            raise ValueError("failure counts and identifiers must match")
        if set(ids) & set(self.failed_pmids):
            raise ValueError("successful and failed PMIDs must be disjoint")
        if self.is_partial != bool(self.failures) or (self.is_partial and not ids):
            raise ValueError("partial success requires both articles and failures")
        return self


class ErrorResponse(BaseModel):
    detail: str
    error_type: str
    failed_pmids: list[str] = Field(default_factory=list)
    failures: dict[str, str] = Field(default_factory=dict)

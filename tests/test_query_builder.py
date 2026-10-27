from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from canine_evidence.config import Settings
from canine_evidence.models.search import SearchRequest
from canine_evidence.query_builder import build_query


@pytest.mark.parametrize("species,clause", [
    ("dog", " AND Dogs[MeSH Terms]"), ("cat", " AND Cats[MeSH Terms]"),
    ("human", " AND Humans[MeSH Terms]"), ("all", ""),
])
def test_species_query(species, clause):
    assert build_query(SearchRequest(gene=" BRAF ", species=species)) == '"BRAF"[tiab]' + clause


def test_filters():
    request = SearchRequest(gene="TP53", cancer_keyword=" melanoma ", year_from=2015, year_to=2020)
    assert build_query(request) == '"TP53"[tiab] AND "melanoma"[tiab] AND 2015:2020[pdat]'
    assert "1800:2020[pdat]" in build_query(SearchRequest(gene="BRAF", year_to=2020))


@pytest.mark.parametrize("kwargs", [
    {"gene": ""}, {"gene": "   "}, {"gene": "A" * 201}, {"gene": 'BRAF" OR Humans[mh]'},
    {"gene": "[]"}, {"gene": "---"}, {"species": "mouse"}, {"limit": 0}, {"limit": 201},
    {"year_from": 2020, "year_to": 2010}, {"year_from": 1799},
    {"year_to": datetime.now(timezone.utc).year + 1}, {"cancer_keyword": 'x" OR y'},
    {"cancer_keyword": "x" * 201},
])
def test_invalid_inputs(kwargs):
    with pytest.raises(ValidationError):
        SearchRequest(**({"gene": "BRAF"} | kwargs))


def test_settings_environment_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    with pytest.raises(ValueError, match="NCBI_EMAIL"):
        Settings.from_env()
    monkeypatch.setenv("NCBI_EMAIL", "unit-test@example.invalid")
    monkeypatch.setenv("NCBI_API_KEY", "test-secret")
    settings = Settings.from_env()
    assert settings.api_key == "test-secret"
    assert "test-secret" not in repr(settings)
    assert "example.invalid" not in repr(settings)


def test_dotenv_and_environment_precedence(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    (tmp_path / ".env").write_text('NCBI_EMAIL="local@example.invalid"\nNCBI_API_KEY=local-key\n')
    assert Settings.from_env().email == "local@example.invalid"
    monkeypatch.setenv("NCBI_EMAIL", "shell@example.invalid")
    assert Settings.from_env().email == "shell@example.invalid"

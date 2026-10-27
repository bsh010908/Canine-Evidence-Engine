from datetime import datetime, timezone

from canine_evidence.models.search import SearchRequest


def build_query(request: SearchRequest) -> str:
    parts = [f'"{request.gene}"[tiab]']
    mesh = {"dog": "Dogs", "cat": "Cats", "human": "Humans"}
    if request.species in mesh:
        parts.append(f"{mesh[request.species]}[MeSH Terms]")
    if request.cancer_keyword:
        parts.append(f'"{request.cancer_keyword}"[tiab]')
    if request.year_from is not None or request.year_to is not None:
        start = request.year_from or 1800
        end = request.year_to or datetime.now(timezone.utc).year
        parts.append(f"{start}:{end}[pdat]")
    return " AND ".join(parts)

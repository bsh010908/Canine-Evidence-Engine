from datetime import datetime, timezone

from canine_evidence.models.search import SearchRequest

# Search-scope filters only; they never confirm the studied species.
# MeSH alone misses records not yet MEDLINE-indexed, so dog/cat also match title
# terms (title, not abstract: abstracts often mention animals in passing).
# "cat" is excluded because it collides with acronyms such as C-CAT, and human
# stays MeSH-only because comparative animal studies routinely say "human" in titles.
SPECIES_FILTERS = {
    "dog": "(Dogs[MeSH Terms] OR dog[ti] OR dogs[ti] OR canine[ti])",
    "cat": "(Cats[MeSH Terms] OR cats[ti] OR feline[ti])",
    "human": "Humans[MeSH Terms]",
}


def build_query(request: SearchRequest) -> str:
    parts = [f'"{request.gene}"[tiab]']
    if request.species in SPECIES_FILTERS:
        parts.append(SPECIES_FILTERS[request.species])
    if request.cancer_keyword:
        parts.append(f'"{request.cancer_keyword}"[tiab]')
    if request.year_from is not None or request.year_to is not None:
        start = request.year_from or 1800
        end = request.year_to or datetime.now(timezone.utc).year
        parts.append(f"{start}:{end}[pdat]")
    return " AND ".join(parts)

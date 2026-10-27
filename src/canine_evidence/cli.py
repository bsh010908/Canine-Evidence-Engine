"""Command-line adapter for the shared search service."""

import argparse
import asyncio
import json
import sys

from pydantic import ValidationError

from canine_evidence.clients.ncbi import NCBIClient, NCBIError
from canine_evidence.config import Settings
from canine_evidence.models.search import SearchRequest
from canine_evidence.search_service import search as search_articles


async def search(request: SearchRequest) -> dict:
    settings = Settings.from_env()
    async with NCBIClient(settings.email, settings.api_key) as client:
        result = await search_articles(request, client)
    return result.model_dump(mode="json")



def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve real PubMed records")
    parser.add_argument("gene")
    parser.add_argument("--species", choices=["dog", "cat", "human", "all"], default="dog")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--cancer-keyword")
    parser.add_argument("--sort", choices=["relevance", "pub_date"], default="relevance")
    args = parser.parse_args()
    try:
        request = SearchRequest(**vars(args))
        result = asyncio.run(search(request))
    except (NCBIError, ValueError, ValidationError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["is_partial"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

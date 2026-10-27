import os
import json
from pathlib import Path
from datetime import datetime

import pytest

from canine_evidence.parsers.pubmed_xml import parse_efetch_xml


@pytest.fixture
def pubmed_fixture():
    directory = Path(__file__).parent / "fixtures" / "pubmed"
    entry = json.loads((directory / "provenance.json").read_text())["records"][0]
    xml = (directory / entry["efetch_file"]).read_text()
    timestamp = datetime.fromisoformat(entry["ncbi_retrieved_at"])
    return entry, xml, timestamp, parse_efetch_xml(xml, retrieved_at=timestamp)


def pytest_collection_modifyitems(items):
    if os.environ.get("NCBI_LIVE_TEST") != "1":
        for item in items:
            if "live_api" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Set NCBI_LIVE_TEST=1 to call real NCBI"))

import copy
import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def response_body():
    body = json.loads((ROOT / "docs/stage2-response-example.json").read_text())
    # Captured before the response echoed sort; that capture used ESearch sort=pub_date.
    return body | {"sort": "pub_date"}


def app():
    return AppTest.from_file(str(ROOT / "frontend/app.py"), default_timeout=10).run()


def submit(at, gene="BRAF"):
    at.text_input(key="gene").set_value(gene)
    return at.button[0].click().run()


def test_search_calls_only_api_and_shows_metadata(monkeypatch, response_body):
    calls = []
    monkeypatch.setenv("CANINE_API_URL", "http://127.0.0.1:9123")
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json=response_body)
    monkeypatch.setattr(httpx, "post", post)
    at = app()
    assert not calls and not at.exception
    at.number_input(key="limit").set_value(3)
    at.number_input(key="year_from").set_value(2020)
    at.number_input(key="year_to").set_value(2026)
    at.text_input(key="cancer_keyword").set_value("melanoma")
    at.selectbox(key="sort").set_value("pub_date")
    submit(at)
    assert not at.exception and not at.error
    assert calls[0][0] == "http://127.0.0.1:9123/search"
    assert calls[0][1]["json"] == {
        "gene": "BRAF", "species": "dog", "limit": 3,
        "year_from": 2020, "year_to": 2026, "cancer_keyword": "melanoma", "sort": "pub_date",
    }
    assert [int(metric.value) for metric in at.metric] == [93, 3]
    text = "\n".join(element.value for element in at.text)
    assert response_body["articles"][0]["pmid"] in text
    assert response_body["articles"][0]["title"] in text
    assert any("unverified" in caption.value for caption in at.caption)
    assert any("출판일 최신순" in caption.value for caption in at.caption)
    assert any("실제 연구 대상 종의 확정" in info.value for info in at.info)
    assert len(at.get("link_button")) == 3


def test_missing_fields_safe(monkeypatch, response_body):
    body = copy.deepcopy(response_body)
    body["articles"][0].update(title=None, authors=[], doi=None, abstract=None,
                               abstract_available=False, journal=None, publication_year=None)
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(200, json=body))
    at = submit(app())
    assert not at.exception
    text = "\n".join(element.value for element in at.text)
    for label in ("제목 정보 없음", "저자 정보 없음", "DOI 없음", "초록 없음", "연도 정보 없음"):
        assert label in text


def test_partial_and_empty_are_distinct(monkeypatch, response_body):
    body = copy.deepcopy(response_body)
    failed = body["articles"].pop()["pmid"]
    body.update(returned_count=2, is_partial=True, failed_count=1,
                failed_pmids=[failed], failures={failed: "NCBITimeoutError"})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(200, json=body))
    at = submit(app())
    assert not at.exception and "부분 성공" in at.warning[0].value
    body.update(articles=[], total_count=0, returned_count=0, is_partial=False,
                failed_count=0, failed_pmids=[], failures={})
    submit(at)
    assert not at.exception and not at.warning
    assert any("설정한 조건에서 검색된 연구 없음" in info.value for info in at.info)


def test_local_validation_does_not_call_server(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid input must not call backend")
    monkeypatch.setattr(httpx, "post", unexpected)
    at = submit(app(), " ")
    assert "입력 검증 실패" in at.error[0].value
    at.number_input(key="year_from").set_value(2025)
    at.number_input(key="year_to").set_value(2020)
    submit(at)
    assert "입력 검증 실패" in at.error[0].value


@pytest.mark.parametrize("status,kind,expected", [
    (422, "validation_error", "입력 검증 실패"),
    (503, "timeout", "NCBI 일시적"),
    (503, "rate_limit", "요청 제한"),
    (502, "server_error", "NCBI 서버"),
    (502, "efetch_all_failed", "전체 수집 실패"),
    (500, "internal_error", "검색 서버 오류"),
])
def test_api_failures(monkeypatch, status, kind, expected):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(
        status, json={"detail": "do-not-display-raw-error", "error_type": kind}))
    at = submit(app())
    assert not at.exception and expected in at.error[0].value
    assert "do-not-display" not in at.error[0].value
    assert not at.metric


@pytest.mark.parametrize("failure,expected", [
    (httpx.ConnectError("private"), "검색 서버에 연결할 수 없습니다"),
    (httpx.ReadTimeout("private"), "대기 시간이 초과"),
])
def test_transport_error_clears_old_results_keeps_inputs(monkeypatch, response_body, failure, expected):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(200, json=response_body))
    at = submit(app())
    assert at.metric
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(httpx, "post", fail)
    submit(at, "TP53")
    assert not at.exception and expected in at.error[0].value
    assert at.text_input(key="gene").value == "TP53"
    assert not at.metric and "private" not in at.error[0].value


def test_invalid_success_body_is_not_empty_success(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(200, text="<html>invalid</html>"))
    at = submit(app())
    assert not at.exception and "응답 형식" in at.error[0].value

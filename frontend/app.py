"""Minimal research UI. Only the FastAPI HTTP boundary is used for searching."""

import os
from datetime import datetime, timezone

import httpx
import streamlit as st
from pydantic import ValidationError

from canine_evidence.models.article import Article
from canine_evidence.models.search import ErrorResponse, SearchRequest, SearchResponse


def fetch_search(request: SearchRequest) -> tuple[SearchResponse | None, str | None]:
    base_url = os.environ.get("CANINE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        response = httpx.post(
            f"{base_url}/search", json=request.model_dump(mode="json"),
            timeout=httpx.Timeout(180.0, connect=5.0),
        )
    except httpx.TimeoutException:
        return None, "응답 대기 시간이 초과되었습니다. 서버에서 검색이 진행 중일 수 있습니다. 잠시 후 다시 시도해 주세요."
    except (httpx.RequestError, httpx.InvalidURL):
        return None, "검색 서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인해 주세요."
    if response.status_code == 200:
        try:
            return SearchResponse.model_validate(response.json()), None
        except (ValueError, ValidationError):
            return None, "검색 서버의 응답 형식이 올바르지 않습니다. 결과를 표시할 수 없습니다."
    try:
        error = ErrorResponse.model_validate(response.json())
        kind = error.error_type
    except (ValueError, ValidationError):
        kind = "unknown"
    if response.status_code == 422:
        return None, "입력 검증 실패: 유전자명, 종, 연도 범위와 결과 개수를 확인해 주세요."
    if kind == "efetch_all_failed":
        return None, "전체 수집 실패: 검색된 논문 데이터를 하나도 불러오지 못했습니다. 잠시 후 재시도해 주세요."
    if response.status_code == 503:
        return None, "NCBI 일시적 연결 오류 또는 요청 제한으로 검색을 완료하지 못했습니다. 잠시 후 재시도해 주세요."
    if response.status_code == 502:
        return None, "NCBI 서버 또는 응답 처리 오류로 검색에 실패했습니다. 검색 결과 없음과는 다른 상태입니다."
    return None, "검색 서버 오류로 검색을 완료하지 못했습니다. 잠시 후 재시도해 주세요."


def render_article(article: Article) -> None:
    with st.container(border=True):
        # Plain text preserves source content without interpreting embedded markup.
        st.text(article.title or "제목 정보 없음")
        st.caption("종 미확인 · unverified")
        st.text(f"저자: {', '.join(article.authors) if article.authors else '저자 정보 없음'}")
        st.text(f"출판연도: {article.publication_year if article.publication_year is not None else '연도 정보 없음'} · 저널: {article.journal or '저널 정보 없음'}")
        st.text(f"PMID: {article.pmid}")
        st.text(f"DOI: {article.doi or 'DOI 없음'}")
        if article.source_url == f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/":
            st.link_button("PubMed 원본 확인 ↗", article.source_url)
        else:
            st.caption("출처 링크를 확인할 수 없습니다.")
        st.caption(f"NCBI 수집 시각 (UTC): {article.ncbi_retrieved_at.astimezone(timezone.utc).isoformat()}")
        with st.expander("초록 보기", expanded=False):
            st.text(article.abstract or "초록 없음")


def render_results(result: SearchResponse) -> None:
    st.subheader("검색 결과")
    left, right = st.columns(2)
    left.metric("전체 검색 건수", result.total_count)
    right.metric("반환된 논문 수", result.returned_count)
    st.caption(f"검색 기준: NCBI PubMed · 검색 시각 (UTC): {result.searched_at.astimezone(timezone.utc).isoformat()}")
    st.text(f"검색식: {result.query_string}")
    if result.is_partial:
        st.warning(f"부분 성공: {result.failed_count}건의 논문 데이터를 불러오지 못했습니다. 아래에는 수집된 논문만 표시합니다.")
        with st.expander("수집 실패 PMID 확인"):
            st.text(", ".join(result.failed_pmids))
    else:
        st.caption("처리 상태: 완료 · 부분 성공 아님")
    if result.warnings:
        with st.expander("PubMed 검색 안내"):
            for messages in result.warnings.values():
                for message in messages:
                    st.text(message)
    if not result.articles:
        st.info("설정한 조건에서 검색된 연구 없음")
        return
    st.info("모든 결과는 종 미확인(unverified)입니다. 종 필터는 MeSH 검색 조건이며 실제 연구 대상 종의 확정을 뜻하지 않습니다.")
    for article in result.articles:
        render_article(article)


def main() -> None:
    st.set_page_config(page_title="Canine Evidence Engine", page_icon="📚", layout="centered")
    st.title("Canine Evidence Engine")
    st.markdown("유전자 관련 문헌을 검색하고, 원본 출처에서 근거를 확인하세요.")
    st.caption("제공된 문헌 범위 기준 · 문헌 탐색 도구이며 진단·치료 판단을 제공하지 않습니다.")
    with st.form("search_form"):
        gene = st.text_input("유전자명", placeholder="예: BRAF 또는 TP53", key="gene", max_chars=200)
        left, right = st.columns(2)
        species = left.selectbox("종 검색 필터 (MeSH)", ["dog", "cat", "human", "all"], key="species")
        limit = right.number_input("결과 개수", min_value=1, max_value=200, value=20, step=1, key="limit")
        st.caption("MeSH 필터는 후보 문헌을 좁히는 조건입니다. 종이 확정되지 않으며, 미색인 문헌은 누락될 수 있습니다.")
        left, right = st.columns(2)
        current_year = datetime.now(timezone.utc).year
        year_from = left.number_input("시작 연도 (선택)", min_value=1800, max_value=current_year, value=None, step=1, key="year_from")
        year_to = right.number_input("종료 연도 (선택)", min_value=1800, max_value=current_year, value=None, step=1, key="year_to")
        cancer_keyword = st.text_input("암종 키워드 (선택)", placeholder="예: melanoma", key="cancer_keyword", max_chars=200)
        submitted = st.form_submit_button("논문 검색", type="primary")
    if submitted:
        # Never show the preceding search's results as if a failed request succeeded.
        st.session_state.pop("search_result", None)
        st.session_state.pop("search_error", None)
        try:
            request = SearchRequest(gene=gene, species=species, limit=limit,
                                    year_from=year_from, year_to=year_to, cancer_keyword=cancer_keyword)
        except ValidationError:
            st.session_state.search_error = "입력 검증 실패: 유전자명을 입력하고 허용 문자 및 연도 범위를 확인해 주세요."
        else:
            with st.spinner("PubMed 논문을 검색하고 있습니다. 잠시 기다려 주세요."):
                result, error = fetch_search(request)
            if error:
                st.session_state.search_error = error
            else:
                st.session_state.search_result = result
    if error := st.session_state.get("search_error"):
        st.error(error)
    if result := st.session_state.get("search_result"):
        render_results(result)
    elif not st.session_state.get("search_error"):
        st.info("유전자명을 입력한 뒤 논문 검색을 눌러 주세요.")


if __name__ == "__main__":
    main()

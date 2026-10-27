import type { SearchRequest, SearchResponse } from "../types";
import ArticleCard from "./ArticleCard";
export default function SearchResults({
  result,
  request,
  busy,
  error,
}: {
  result: SearchResponse | null;
  request: SearchRequest | null;
  busy: boolean;
  error: string;
}) {
  const initial = !request && !result && !busy && !error;
  return (
    <section className="results" aria-label="논문 검색 결과" aria-busy={busy}>
      <div className="results-heading">
        {initial ? (
          <h1>검색 결과</h1>
        ) : (
          <div>
            <h1><span className="gene-heading">{request?.gene}</span> 검색 결과</h1>
          </div>
        )}
        {!initial && <span className="database-label">PubMed</span>}
      </div>
      <div aria-live="polite">
        {busy ? (
          <div className="loading-state">
            <div className="flex items-center gap-3">
              <span className="spinner" />
              <p>PubMed에서 논문을 수집하고 있습니다.</p>
            </div>
            {[1, 2, 3].map((i) => (
              <div className="skeleton motion-safe:animate-pulse" key={i}>
                <div />
                <div />
                <div />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="state-message error-state" role="alert">
            <span className="state-symbol">!</span>
            <h2>검색을 완료하지 못했습니다</h2>
            <p>{error}</p>
            <p className="muted">
              조건은 유지되었습니다. 상단 검색 버튼으로 다시 시도할 수 있습니다.
            </p>
          </div>
        ) : result ? (
          <>
            <div className="result-meta">
              <p>
                전체 검색 <strong>{result.total_count.toLocaleString()}</strong>
                건 <span> / </span> 표시{" "}
                <strong>{result.returned_count}</strong>건
              </p>
              <span>출판연도 내림차순</span>
            </div>
            <div className="evidence-note">
              <span aria-hidden="true">ⓘ</span>
              <p>
                모든 결과는 <strong>종 미확인(unverified)</strong> 상태입니다.
                MeSH 필터는 실제 연구 대상 종의 확정을 뜻하지 않습니다.
              </p>
            </div>
            {result.is_partial && (
              <div className="partial-note" role="status">
                <strong>일부 논문만 수집되었습니다</strong>
                <p>
                  {result.failed_count}건 수집 실패 · 아래에는 성공한 논문을
                  표시합니다.
                </p>
                <details>
                  <summary>실패 PMID 확인</summary>
                  {result.failed_pmids.join(", ")}
                </details>
              </div>
            )}
            <details className="search-details">
              <summary>
                검색 상세 <span>검색 시각 · 검색식</span>
              </summary>
              <p>검색 시각 (UTC): {result.searched_at}</p>
              <p>검색식: {result.query_string}</p>
              <p>PubMed 해석: {result.query_translation}</p>
              {Object.values(result.warnings)
                .flat()
                .map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
            </details>
            {result.articles.length ? (
              <div className="article-list">
                {result.articles.map((a, i) => (
                  <ArticleCard key={a.pmid} article={a} index={i} />
                ))}
              </div>
            ) : (
              <div className="state-message">
                <span className="state-symbol">⌕</span>
                <h2>설정한 조건에서 검색된 연구 없음</h2>
                <p>유전자명 또는 상세 조건을 조정해 다시 검색해 주세요.</p>
              </div>
            )}
          </>
        ) : (
          <p className="initial-guidance">
            <span className="desktop-guidance">위에서</span>
            <span className="mobile-guidance">위에서</span> 유전자명을 입력하고 검색해 주세요.
          </p>
        )}
      </div>
    </section>
  );
}

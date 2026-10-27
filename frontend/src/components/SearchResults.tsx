import { SORT_LABELS, type SearchRequest, type SearchResponse } from "../types";
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
  const warnings = result ? Object.values(result.warnings).flat() : [];
  return (
    <section className="results" aria-label="논문 검색 결과" aria-busy={busy}>
      <div className="results-heading">
        <h1>
          <span className="gene-heading">{request?.gene}</span> 검색 결과
        </h1>
        {result && !busy && !error && (
          <p className="result-count">
            PubMed 검색 결과 <strong>{result.total_count.toLocaleString()}</strong>건
            <span aria-hidden="true"> · </span>
            {SORT_LABELS[result.sort]} 상위 <strong>{result.returned_count}</strong>건 표시
          </p>
        )}
      </div>
      <div aria-live="polite">
        {busy ? (
          <div className="loading-state">
            <p className="loading-message">
              <span className="spinner" aria-hidden="true" />
              PubMed에서 논문을 가져오고 있습니다.
            </p>
            {[1, 2, 3].map((i) => (
              <div className="skeleton motion-safe:animate-pulse" key={i} aria-hidden="true">
                <div />
                <div />
                <div />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="state-message error-state" role="alert">
            <h2>검색을 완료하지 못했습니다</h2>
            <p>{error}</p>
            <p className="muted">
              입력한 조건은 그대로 유지됩니다. 검색 버튼을 눌러 다시 시도해 주세요.
            </p>
          </div>
        ) : result ? (
          <>
            <p className="evidence-note">
              종 필터는 검색 범위를 좁히는 조건입니다. 각 논문의 실제 연구 대상
              종은 확인되지 않았으므로(unverified) 원문에서 확인해 주세요.
            </p>
            {result.is_partial && (
              <div className="partial-note" role="status">
                <p>
                  <strong>일부 논문만 가져왔습니다.</strong>{" "}
                  {result.failed_count}건을 불러오지 못해 나머지{" "}
                  {result.returned_count}건만 표시합니다.
                </p>
                <details>
                  <summary>불러오지 못한 PMID</summary>
                  <p>{result.failed_pmids.join(", ")}</p>
                </details>
              </div>
            )}
            <details className="search-details">
              <summary>검색 상세 (검색식 · 검색 시각)</summary>
              <dl>
                <dt>검색식</dt>
                <dd>{result.query_string}</dd>
                <dt>PubMed 해석</dt>
                <dd>{result.query_translation}</dd>
                <dt>정렬</dt>
                <dd>
                  {result.sort === "relevance"
                    ? "PubMed 관련도순. 검색 결과가 많으면 같은 검색에서도 상위 순서가 달라질 수 있습니다."
                    : "PubMed 출판일 최신순"}
                </dd>
                <dt>검색 시각 (UTC)</dt>
                <dd>{result.searched_at}</dd>
              </dl>
              {warnings.map((w, i) => (
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
                <h2>설정한 조건에서 검색된 연구 없음</h2>
                <p>유전자명 또는 검색 조건을 조정해 다시 검색해 주세요.</p>
              </div>
            )}
          </>
        ) : null}
      </div>
    </section>
  );
}

import { useState } from "react";
import type { Article } from "../types";
export default function ArticleCard({
  article,
  index,
}: {
  article: Article;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [allAuthors, setAllAuthors] = useState(false);
  const validSource =
    article.source_url === `https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`;
  const abstractId = `abstract-${article.pmid}`;
  return (
    <article className="article-card">
      <p className="article-meta">
        <span className="article-index">{index + 1}</span>
        <span className="journal">{article.journal || "저널 정보 없음"}</span>
        <span className="year">{article.publication_year ?? "연도 없음"}</span>
      </p>
      <h3>{article.title || "제목 정보 없음"}</h3>
      <p className="authors">
        {article.authors.length
          ? (allAuthors ? article.authors : article.authors.slice(0, 3)).join(
              ", ",
            )
          : "저자 정보 없음"}
        {article.authors.length > 3 && (
          <button
            type="button"
            className="text-button"
            aria-expanded={allAuthors}
            onClick={() => setAllAuthors(!allAuthors)}
          >
            {allAuthors ? "접기" : `외 ${article.authors.length - 3}명`}
          </button>
        )}
      </p>
      {article.abstract_available && article.abstract ? (
        <div className="abstract">
          <p id={abstractId} className={expanded ? "" : "line-clamp-3"}>
            {article.abstract}
          </p>
          <button
            type="button"
            className="text-button"
            aria-expanded={expanded}
            aria-controls={abstractId}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "초록 접기" : "초록 펼치기"}
          </button>
        </div>
      ) : (
        <p className="abstract muted">초록 없음</p>
      )}
      <div className="article-footer">
        <dl className="identifiers">
          <div>
            <dt>PMID</dt>
            <dd>{article.pmid}</dd>
          </div>
          <div>
            <dt>DOI</dt>
            <dd>{article.doi || "정보 없음"}</dd>
          </div>
        </dl>
        <span className="species-badge">연구 대상 종 미확인</span>
        {validSource ? (
          <a
            className="source-link"
            href={article.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            PubMed 원본 <span aria-hidden="true">↗</span>
          </a>
        ) : (
          <span className="muted">출처 링크 확인 불가</span>
        )}
      </div>
      <details className="record-details">
        <summary>수집 정보</summary>
        <p>종 상태: unverified · 증거 강도: low</p>
        <p>NCBI 수집 시각 (UTC): {article.ncbi_retrieved_at}</p>
        {article.mesh_terms.length > 0 && (
          <p>MeSH: {article.mesh_terms.join(" · ")}</p>
        )}
      </details>
    </article>
  );
}

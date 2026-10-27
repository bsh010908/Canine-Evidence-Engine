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
  return (
    <article className="article-card">
      <div className="article-top">
        <span className="article-index">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="journal">{article.journal || "저널 정보 없음"}</span>
        <span className="year">{article.publication_year ?? "연도 없음"}</span>
      </div>
      <h3>{article.title || "제목 정보 없음"}</h3>
      <p className="authors">
        {article.authors.length
          ? (allAuthors ? article.authors : article.authors.slice(0, 3)).join(
              ", ",
            )
          : "저자 정보 없음"}
        {article.authors.length > 3 && (
          <button onClick={() => setAllAuthors(!allAuthors)}>
            {allAuthors ? "접기" : `외 ${article.authors.length - 3}명`}
          </button>
        )}
      </p>
      <div className="abstract">
        <span className="eyebrow">ABSTRACT</span>
        {article.abstract_available && article.abstract ? (
          <>
            <p className={expanded ? "" : "line-clamp-3"}>{article.abstract}</p>
            <button
              className="text-button"
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "초록 접기 −" : "전체 초록 보기 +"}
            </button>
          </>
        ) : (
          <p className="muted">초록 없음</p>
        )}
      </div>
      <div className="identifiers">
        <span>
          PMID <strong>{article.pmid}</strong>
        </span>
        <span>
          DOI <strong>{article.doi || "정보 없음"}</strong>
        </span>
      </div>
      <div className="article-footer">
        <span className="species-badge">
          <span aria-hidden="true">○</span> 연구 대상 종 미확인
        </span>
        {validSource ? (
          <a
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

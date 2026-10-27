import type { Article, SearchRequest, SearchResponse } from "./types";
const object = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((x) => typeof x === "string");
const nullableText = (v: unknown) => v === null || typeof v === "string";
const date = (v: unknown) =>
  typeof v === "string" &&
  /(?:Z|[+-]\d{2}:\d{2})$/.test(v) &&
  Number.isFinite(Date.parse(v));
function article(v: unknown): v is Article {
  return (
    object(v) &&
    typeof v.pmid === "string" &&
    /^[1-9]\d*$/.test(v.pmid) &&
    ["title", "doi", "abstract", "journal"].every((k) => nullableText(v[k])) &&
    strings(v.authors) &&
    strings(v.mesh_terms) &&
    strings(v.publication_types) &&
    strings(v.species_evidence_notes) &&
    typeof v.abstract_available === "boolean" &&
    (v.publication_year === null || Number.isInteger(v.publication_year)) &&
    typeof v.source_url === "string" &&
    date(v.ncbi_retrieved_at) &&
    v.species_status === "unverified" &&
    v.species_evidence_strength === "low"
  );
}
export function parseSearchResponse(v: unknown): SearchResponse {
  if (
    !object(v) ||
    !Array.isArray(v.articles) ||
    !v.articles.every(article) ||
    !Number.isInteger(v.total_count) ||
    !Number.isInteger(v.returned_count) ||
    (v.total_count as number) < (v.returned_count as number) ||
    (v.returned_count as number) > 200 ||
    v.returned_count !== v.articles.length ||
    !date(v.searched_at) ||
    !date(v.esearch_retrieved_at) ||
    typeof v.query_string !== "string" ||
    typeof v.query_translation !== "string" ||
    typeof v.is_partial !== "boolean" ||
    !strings(v.failed_pmids) ||
    !Number.isInteger(v.failed_count) ||
    !object(v.failures) ||
    !Object.values(v.failures).every((x) => typeof x === "string") ||
    !object(v.warnings) ||
    !Object.values(v.warnings).every(strings) ||
    v.from_cache !== false ||
    !nullableText(v.message)
  )
    throw new Error(
      "검색 응답 형식을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    );
  const ids = v.articles.map((a) => a.pmid);
  const failed = Object.keys(v.failures);
  if (
    new Set(ids).size !== ids.length ||
    v.failed_count !== failed.length ||
    JSON.stringify(v.failed_pmids) !== JSON.stringify(failed) ||
    failed.some((id) => ids.includes(id)) ||
    v.is_partial !== Boolean(failed.length) ||
    (v.is_partial && !ids.length)
  )
    throw new Error(
      "검색 응답의 건수가 일치하지 않습니다. 다시 시도해 주세요.",
    );
  return v as unknown as SearchResponse;
}
export async function search(
  request: SearchRequest,
  signal: AbortSignal,
): Promise<SearchResponse> {
  let response: Response;
  try {
    response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch {
    throw new Error(
      signal.aborted
        ? "응답 대기 시간이 초과되었습니다. 서버에서 검색이 계속 진행 중일 수 있습니다."
        : "검색 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.",
    );
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error(
      "서버 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.",
    );
  }
  if (response.ok) return parseSearchResponse(body);
  const kind = object(body) ? body.error_type : "";
  if (kind === "efetch_all_failed")
    throw new Error(
      "전체 수집 실패: 검색된 논문을 불러오지 못했습니다. 잠시 후 다시 검색해 주세요.",
    );
  if (response.status === 422)
    throw new Error("입력 검증 실패: 검색 조건의 문자와 범위를 확인해 주세요.");
  if (response.status === 503)
    throw new Error(
      "NCBI 연결 지연 또는 요청 제한이 발생했습니다. 잠시 후 다시 검색해 주세요.",
    );
  if (response.status === 502)
    throw new Error(
      "NCBI 응답 처리에 실패했습니다. 검색 결과가 없는 상태와는 다릅니다.",
    );
  throw new Error("검색 서버 오류가 발생했습니다. 잠시 후 다시 검색해 주세요.");
}

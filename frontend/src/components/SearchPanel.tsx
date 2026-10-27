import { useState, type FormEvent } from "react";
import type { SearchRequest, Species } from "../types";
export default function SearchPanel({ busy, initial, onSearch }: {
  busy: boolean; initial: boolean; onSearch: (r: SearchRequest) => void;
}) {
  const [gene, setGene] = useState("");
  const [species, setSpecies] = useState<Species>("all");
  const [period, setPeriod] = useState("all");
  const [fromValue, setFromValue] = useState("");
  const [toValue, setToValue] = useState("");
  const [keywordValue, setKeywordValue] = useState("");
  const [limit, setLimit] = useState("20");
  const [error, setError] = useState("");
  const currentYear = new Date().getUTCFullYear();
  function submit(event?: FormEvent<HTMLFormElement>, selectedGene = gene) {
    event?.preventDefault();
    if (busy) return;
    const from = period === "custom" && fromValue ? Number(fromValue) : null;
    const to = period === "custom" && toValue ? Number(toValue) : null;
    const keyword = keywordValue.trim();
    if (!/^[A-Za-z0-9/ -]+$/.test(selectedGene.trim()) || !/[A-Za-z0-9]/.test(selectedGene)) {
      setError("유전자명에 영문·숫자·공백·하이픈·슬래시를 입력해 주세요."); return;
    }
    if ([from, to].some(y => y !== null && (!Number.isInteger(y) || y < 1800 || y > currentYear))) {
      setError(`연도는 1800부터 ${currentYear}까지 입력해 주세요.`); return;
    }
    if (from !== null && to !== null && from > to) {
      setError("시작 연도는 종료 연도보다 늦을 수 없습니다."); return;
    }
    if (keyword && !/^[\p{L}\p{N} /-]+$/u.test(keyword)) {
      setError("암종 키워드의 특수문자를 확인해 주세요."); return;
    }
    setError("");
    onSearch({ gene: selectedGene.trim(), species, limit: Number(limit), year_from: from, year_to: to, cancer_keyword: keyword || null });
  }
  function resetFilters() {
    setSpecies("all"); setPeriod("all"); setFromValue(""); setToValue("");
    setKeywordValue(""); setLimit("20"); setError("");
  }
  return (
    <>
      <section className="search-band" aria-label="검색 조건">
        <form className="content-width" onSubmit={submit}>
          <label className="search-label" htmlFor="gene">유전자 문헌 검색</label>
          <div className="primary-search">
            <div className="gene-input">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/></svg>
              <input id="gene" aria-label="유전자명" value={gene} onChange={e => setGene(e.target.value)} placeholder="유전자명을 입력하세요 · 예: BRAF, TP53" maxLength={200} required aria-describedby={error ? "input-error" : undefined}/>
            </div>
            <button className="search-button" aria-label={busy ? "검색 중" : "논문 검색"} disabled={busy}>{busy ? "검색 중…" : "검색"}</button>
          </div>
          <div className="search-options">
            <fieldset className="species-filter">
              <legend>종 (MeSH)</legend>
              <div className="species-grid">
                {([["all", "전체"], ["dog", "개"], ["cat", "고양이"], ["human", "사람"]] as const).map(([value, label]) => (
                  <label key={value} className={species === value ? "selected" : ""}>
                    <input type="radio" name="species" value={value} checked={species === value} onChange={() => setSpecies(value)}/>{label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="filter-control"><label htmlFor="period">발행 연도</label><select id="period" value={period} onChange={e => setPeriod(e.target.value)}><option value="all">전체 기간</option><option value="custom">기간 지정</option></select></div>
            <div className="filter-control cancer-filter"><label htmlFor="cancer">암종</label><input id="cancer" aria-label="암종 키워드" value={keywordValue} onChange={e => setKeywordValue(e.target.value)} maxLength={200} placeholder="전체 · 키워드 입력"/></div>
            <button type="button" className="reset-button" onClick={resetFilters}>조건 초기화</button>
          </div>
          {period === "custom" && <div className="year-grid">
            <label>시작 연도<input type="number" value={fromValue} onChange={e => setFromValue(e.target.value)} min="1800" max={currentYear} placeholder="제한 없음"/></label>
            <span aria-hidden="true">—</span>
            <label>종료 연도<input type="number" value={toValue} onChange={e => setToValue(e.target.value)} min="1800" max={currentYear} placeholder="제한 없음"/></label>
          </div>}
          <details className="fetch-options"><summary>수집 옵션</summary><label htmlFor="limit">가져올 논문 수</label><select id="limit" value={limit} onChange={e => setLimit(e.target.value)}>{[3,10,20,50,100,200].map(n => <option key={n} value={n}>{n}건</option>)}</select></details>
          {error && <p id="input-error" role="alert" className="field-error">{error}</p>}
        </form>
      </section>
      {initial && <section className="welcome content-width" aria-labelledby="welcome-title">
        <p className="welcome-kicker">검색 시작하기</p>
        <h1 id="welcome-title">어떤 유전자를 찾고 계신가요?</h1>
        <p>유전자 기호를 입력해 PubMed 연구 문헌과 원본 출처를 탐색하세요.</p>
        <div className="examples"><span>빠른 검색</span>{["BRAF", "TP53"].map(value => <button key={value} type="button" disabled={busy} onClick={() => { setGene(value); submit(undefined, value); }}>{value}<span aria-hidden="true">→</span></button>)}</div>
      </section>}
    </>
  );
}

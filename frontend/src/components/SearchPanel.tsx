import { useState, type FormEvent } from "react";
import type { SearchRequest, Species } from "../types";
const DEFAULT_LIMIT = "20";
export default function SearchPanel({ busy, initial, onSearch }: {
  busy: boolean; initial: boolean; onSearch: (r: SearchRequest) => void;
}) {
  const [gene, setGene] = useState("");
  const [species, setSpecies] = useState<Species>("all");
  const [period, setPeriod] = useState("all");
  const [fromValue, setFromValue] = useState("");
  const [toValue, setToValue] = useState("");
  const [keywordValue, setKeywordValue] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const currentYear = new Date().getUTCFullYear();
  const activeFilters = [species !== "all", period === "custom", keywordValue.trim() !== ""].filter(Boolean).length;
  const isDefault = activeFilters === 0 && limit === DEFAULT_LIMIT && !fromValue && !toValue;
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
    setKeywordValue(""); setLimit(DEFAULT_LIMIT); setError("");
  }
  return (
    <section className={`search-band${initial ? " initial" : ""}`} aria-label="검색 조건">
      <form className="content-width" onSubmit={submit} noValidate>
        {initial && <h1 className="search-title">유전자 문헌 검색</h1>}
        <div className="primary-search">
          <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/></svg>
          <input id="gene" type="text" enterKeyHint="search" aria-label="유전자명" value={gene} onChange={e => setGene(e.target.value)} placeholder="유전자 기호 입력" maxLength={200} required autoComplete="off" spellCheck={false} aria-invalid={error ? true : undefined} aria-describedby={error ? "input-error" : undefined}/>
          <button className="search-button" aria-label={busy ? "검색 중" : "논문 검색"} disabled={busy}>{busy ? "검색 중…" : "검색"}</button>
        </div>
        {initial && <div className="examples">
          <span id="examples-label">예시</span>
          {["BRAF", "TP53"].map(value => <button key={value} type="button" aria-describedby="examples-label" disabled={busy} onClick={() => { setGene(value); submit(undefined, value); }}>{value}</button>)}
        </div>}
        {error && <p id="input-error" role="alert" className="field-error">{error}</p>}
        <button type="button" className="filters-toggle" aria-expanded={filtersOpen} aria-controls="search-options" onClick={() => setFiltersOpen(!filtersOpen)}>
          검색 조건{activeFilters > 0 && <span className="filter-count">{activeFilters}개 적용</span>}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="m3 4.5 3 3 3-3"/></svg>
        </button>
        <div id="search-options" className={`search-options${filtersOpen ? " open" : ""}`}>
          <fieldset className="field species-filter">
            <legend className="field-label">종 (MeSH)</legend>
            <div className="segmented">
              {([["all", "전체"], ["dog", "개"], ["cat", "고양이"], ["human", "사람"]] as const).map(([value, label]) => (
                <label key={value} className={species === value ? "selected" : ""}>
                  <input type="radio" name="species" value={value} checked={species === value} onChange={() => setSpecies(value)}/>{label}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="field period-filter">
            <label className="field-label" htmlFor="period">발행 연도</label>
            <div className="period-controls">
              <select id="period" value={period} onChange={e => setPeriod(e.target.value)}><option value="all">전체 기간</option><option value="custom">기간 지정</option></select>
              {period === "custom" && <>
                <input type="number" inputMode="numeric" aria-label="시작 연도" value={fromValue} onChange={e => setFromValue(e.target.value)} min="1800" max={currentYear} placeholder="시작"/>
                <span aria-hidden="true">–</span>
                <input type="number" inputMode="numeric" aria-label="종료 연도" value={toValue} onChange={e => setToValue(e.target.value)} min="1800" max={currentYear} placeholder="종료"/>
              </>}
            </div>
          </div>
          <div className="field cancer-filter">
            <div className="field-label"><label htmlFor="cancer">암종 키워드</label><span id="cancer-hint" className="optional">직접 입력</span></div>
            <input id="cancer" aria-describedby="cancer-hint" value={keywordValue} onChange={e => setKeywordValue(e.target.value)} maxLength={200} placeholder="예: melanoma, lymphoma"/>
          </div>
          <div className="field limit-filter">
            <label className="field-label" htmlFor="limit">결과 수</label>
            <select id="limit" value={limit} onChange={e => setLimit(e.target.value)}>{[3, 10, 20, 50, 100, 200].map(n => <option key={n} value={n}>{n}건</option>)}</select>
          </div>
          <button type="button" className="reset-button" onClick={resetFilters} disabled={isDefault}>조건 초기화</button>
        </div>
        {initial && <p className="filter-note">종 (MeSH) 필터는 PubMed 색인 기준이며, 논문의 실제 연구 대상 종을 확정하지 않습니다.</p>}
      </form>
    </section>
  );
}

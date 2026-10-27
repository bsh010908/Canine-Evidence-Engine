import { useEffect, useRef, useState } from "react";
import { search } from "./api";
import type { SearchRequest, SearchResponse } from "./types";
import SearchPanel from "./components/SearchPanel";
import SearchResults from "./components/SearchResults";
export default function App() {
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [request, setRequest] = useState<SearchRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function onSearch(input: SearchRequest) {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setRequest(input);
    setBusy(true);
    setError("");
    setResult(null);
    const timeout = setTimeout(() => controller.abort(), 180_000);
    try {
      const data = await search(input, controller.signal);
      if (active.current === controller) setResult(data);
    } catch (e) {
      if (active.current === controller)
        setError(e instanceof Error ? e.message : "검색에 실패했습니다.");
    } finally {
      clearTimeout(timeout);
      if (active.current === controller) setBusy(false);
    }
  }
  const initial = request === null;
  return (
    <>
      <a className="skip-link" href={initial ? "#gene" : "#results"}>
        {initial ? "검색창으로 이동" : "검색 결과로 이동"}
      </a>
      <header className="site-header">
        <div className="header-inner">
          <div className="brand"><span className="brand-mark" aria-hidden="true">CE</span><span>Canine Evidence Engine</span></div>
          <div className="header-section">문헌 탐색</div>
          <a className="help-link" href="#search-guide">검색 안내</a>
        </div>
      </header>
      <main>
        <SearchPanel initial={initial} busy={busy} onSearch={onSearch} />
        {!initial && (
          <div id="results" className="content-width result-area" tabIndex={-1}>
            <SearchResults
              result={result}
              request={request}
              busy={busy}
              error={error}
            />
          </div>
        )}
        <section id="search-guide" className="search-guide content-width">
          <h2>검색 범위 안내</h2>
          <div><p>종·발행 연도·암종 키워드로 검색 범위를 좁힐 수 있습니다.</p>
          <p>MeSH 종 필터는 실제 연구 대상 종을 확정하지 않습니다. 연구 대상은 논문 원문에서 확인하세요.</p></div>
        </section>
      </main>
      <footer className="site-footer">
        <span>데이터 출처 <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener noreferrer">NCBI PubMed ↗</a></span>
        <p>연구 문헌 탐색 도구 · 진단 및 치료 판단을 제공하지 않습니다.</p>
      </footer>
    </>
  );
}

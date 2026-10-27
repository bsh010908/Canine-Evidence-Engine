import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import fixture from "../../../docs/stage2-response-example.json";
import { parseSearchResponse, search } from "../api";
import App from "../App";
import SearchResults from "../components/SearchResults";
const request = {
  gene: "BRAF",
  species: "dog" as const,
  limit: 3,
  year_from: null,
  year_to: null,
  cancer_keyword: null,
  sort: "relevance" as const,
};
// The captured response predates the sort echo; it was retrieved with ESearch sort=pub_date.
const data = () => ({ ...structuredClone(fixture), sort: "pub_date" });
function mockResponse(body: unknown, status = 200) {
  const mock = vi
    .fn()
    .mockImplementation(
      async () => new Response(JSON.stringify(body), { status }),
    );
  vi.stubGlobal("fetch", mock);
  return mock;
}
describe("API contract", () => {
  it("accepts the captured real response", () => {
    expect(parseSearchResponse(data()).returned_count).toBe(3);
  });
  it.each(["count", "duplicate", "species", "date", "failure", "missing", "sort"])(
    "rejects malformed response: %s",
    (kind) => {
      const body = data();
      if (kind === "count") body.returned_count = 99;
      if (kind === "duplicate") body.articles[1].pmid = body.articles[0].pmid;
      if (kind === "species") body.articles[0].species_status = "dog_confirmed";
      if (kind === "date") body.searched_at = "bad-date";
      if (kind === "failure") body.failed_count = 1;
      if (kind === "missing") delete (body as Partial<typeof body>).articles;
      if (kind === "sort") body.sort = "date";
      expect(() => parseSearchResponse(body)).toThrow();
    },
  );
  it.each([
    [422, "validation_error", "입력 검증"],
    [503, "rate_limit", "요청 제한"],
    [502, "server_error", "응답 처리"],
    [502, "efetch_all_failed", "전체 수집 실패"],
    [500, "internal_error", "검색 서버 오류"],
  ])("maps HTTP %s %s", async (status, error_type, message) => {
    mockResponse(
      { error_type, detail: "secret-must-not-be-shown" },
      Number(status),
    );
    await expect(search(request, new AbortController().signal)).rejects.toThrow(
      String(message),
    );
  });
  it("handles network failure and timeout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("sensitive detail")),
    );
    const controller = new AbortController();
    await expect(search(request, controller.signal)).rejects.toThrow(
      "연결할 수 없습니다",
    );
    controller.abort();
    await expect(search(request, controller.signal)).rejects.toThrow(
      "대기 시간이 초과",
    );
  });
  it("rejects non-JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json")));
    await expect(search(request, new AbortController().signal)).rejects.toThrow(
      "응답을 읽을 수 없습니다",
    );
  });
});
describe("search UI", () => {
  it("starts without invented articles and submits current filters through the proxy", async () => {
    const mock = mockResponse(data());
    render(<App />);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/유전자명/), {
      target: { value: "BRAF" },
    });
    fireEvent.change(screen.getByLabelText("결과 수"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await screen.findByText(fixture.articles[0].title);
    expect(mock.mock.calls[0][0]).toBe("/api/search");
    expect(JSON.parse(mock.mock.calls[0][1].body)).toEqual({ ...request, species: "all" });
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(
      screen.getAllByRole("link", { name: /PubMed 원본/ })[0],
    ).toHaveAttribute("href", fixture.articles[0].source_url);
    expect(screen.getAllByText("연구 대상 종 미확인")).toHaveLength(3);
    fireEvent.click(
      screen.getAllByRole("button", { name: "초록 펼치기" })[0],
    );
    expect(screen.getByRole("button", { name: "초록 접기" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
  it("supports optional filters and validates reversed dates without HTTP", async () => {
    const mock = mockResponse(data());
    render(<App />);
    fireEvent.change(screen.getByLabelText(/유전자명/), {
      target: { value: "TP53" },
    });
    fireEvent.change(screen.getByLabelText("발행 연도"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("시작 연도"), {
      target: { value: "2025" },
    });
    fireEvent.change(screen.getByLabelText("종료 연도"), {
      target: { value: "2024" },
    });
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    expect(screen.getByRole("alert")).toHaveTextContent("시작 연도");
    expect(mock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("종료 연도"), {
      target: { value: "2026" },
    });
    fireEvent.change(screen.getByLabelText("암종 키워드"), {
      target: { value: "melanoma" },
    });
    fireEvent.click(screen.getByLabelText("사람"));
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await waitFor(() => expect(mock).toHaveBeenCalledOnce());
    expect(JSON.parse(mock.mock.calls[0][1].body)).toMatchObject({
      gene: "TP53",
      species: "human",
      year_from: 2025,
      year_to: 2026,
      cancer_keyword: "melanoma",
    });
  });
  it("safely renders absent metadata and rejects unsafe source links", () => {
    const body = data();
    const a = body.articles[0];
    a.title = null as unknown as string;
    a.authors = [];
    a.doi = null;
    a.abstract = null as unknown as string;
    a.abstract_available = false;
    a.source_url = "javascript:alert(1)";
    render(
      <SearchResults
        result={parseSearchResponse(body)}
        request={request}
        busy={false}
        error=""
      />,
    );
    expect(screen.getByText("제목 정보 없음")).toBeInTheDocument();
    expect(screen.getByText("초록 없음")).toBeInTheDocument();
    expect(screen.getByText("출처 링크 확인 불가")).toBeInTheDocument();
  });
  it("distinguishes partial success from an empty result", () => {
    const body = {
      ...data(),
      is_partial: true,
      failed_pmids: ["123"],
      failed_count: 1,
      failures: { 123: "timeout" },
    };
    const { rerender } = render(
      <SearchResults
        result={parseSearchResponse(body)}
        request={request}
        busy={false}
        error=""
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("일부 논문만");
    expect(screen.getAllByRole("article")).toHaveLength(3);
    rerender(
      <SearchResults
        result={parseSearchResponse({
          ...data(),
          articles: [],
          total_count: 0,
          returned_count: 0,
        })}
        request={request}
        busy={false}
        error=""
      />,
    );
    expect(
      screen.getByText("설정한 조건에서 검색된 연구 없음"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });
  it("shows loading, prevents duplicate submission, clears old results on failure and retains input", async () => {
    const mock = mockResponse(data());
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "BRAF" }));
    await screen.findByText(fixture.articles[0].title);
    let reject!: (e: Error) => void;
    mock.mockImplementationOnce(
      () =>
        new Promise((_, r) => {
          reject = r;
        }),
    );
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    expect(screen.getByRole("button", { name: /검색 중/ })).toBeDisabled();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    reject(new Error("secret"));
    await screen.findByRole("alert");
    expect(screen.getByLabelText(/유전자명/)).toHaveValue("BRAF");
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});

describe("search screen transition", () => {
  it("sends the chosen sort and labels results with the sort the server used", async () => {
    const mock = mockResponse(data());
    render(<App />);
    expect(screen.getByLabelText("정렬")).toHaveValue("relevance");
    fireEvent.change(screen.getByLabelText(/유전자명/), { target: { value: "BRAF" } });
    fireEvent.change(screen.getByLabelText("정렬"), { target: { value: "pub_date" } });
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await screen.findByText(fixture.articles[0].title);
    expect(JSON.parse(mock.mock.calls[0][1].body).sort).toBe("pub_date");
    expect(screen.getByText(/출판일 최신순 상위/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "조건 초기화" }));
    expect(screen.getByLabelText("정렬")).toHaveValue("relevance");
  });
  it("enables reset only when conditions differ from defaults and restores them", () => {
    render(<App />);
    const reset = screen.getByRole("button", { name: "조건 초기화" });
    expect(reset).toBeDisabled();
    fireEvent.click(screen.getByLabelText("개"));
    fireEvent.change(screen.getByLabelText("암종 키워드"), {
      target: { value: "lymphoma" },
    });
    expect(reset).toBeEnabled();
    fireEvent.click(reset);
    expect(screen.getByLabelText("전체")).toBeChecked();
    expect(screen.getByLabelText("암종 키워드")).toHaveValue("");
    expect(reset).toBeDisabled();
  });
  it("starts with a single search heading and quick search opens results", async () => {
    const mock = mockResponse(data());
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "유전자 문헌 검색" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "논문 검색 결과" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "BRAF" }));
    await screen.findByRole("heading", { name: "BRAF 검색 결과" });
    await screen.findByText(fixture.articles[0].title);
    expect(mock).toHaveBeenCalledOnce();
    expect(JSON.parse(mock.mock.calls[0][1].body).gene).toBe("BRAF");
    expect(
      screen.queryByRole("heading", { name: "유전자 문헌 검색" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText(/유전자명/)).toHaveValue("BRAF");
  });
  it("preserves every filter across first search, failure, and retry", async () => {
    const mock = mockResponse(data());
    render(<App />);
    fireEvent.change(screen.getByLabelText("발행 연도"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText(/유전자명/), {
      target: { value: "TP53" },
    });
    fireEvent.click(screen.getByLabelText("사람"));
    fireEvent.change(screen.getByLabelText("결과 수"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText("시작 연도"), {
      target: { value: "2020" },
    });
    fireEvent.change(screen.getByLabelText("종료 연도"), {
      target: { value: "2025" },
    });
    fireEvent.change(screen.getByLabelText("암종 키워드"), {
      target: { value: "melanoma" },
    });
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await screen.findByText(fixture.articles[0].title);
    expect(screen.getByLabelText("사람")).toBeChecked();
    expect(screen.getByLabelText("시작 연도")).toHaveValue(2020);
    expect(screen.getByLabelText("종료 연도")).toHaveValue(2025);
    expect(screen.getByLabelText("암종 키워드")).toHaveValue("melanoma");
    expect(screen.getByLabelText("결과 수")).toHaveValue("3");
    mock.mockRejectedValueOnce(new Error("offline"));
    fireEvent.change(screen.getByLabelText(/유전자명/), {
      target: { value: "BRAF" },
    });
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText(/유전자명/)).toHaveValue("BRAF");
    expect(screen.getByLabelText("암종 키워드")).toHaveValue("melanoma");
    fireEvent.click(screen.getByRole("button", { name: "논문 검색" }));
    await screen.findByText(fixture.articles[0].title);
    expect(mock).toHaveBeenCalledTimes(3);
    expect(JSON.parse(mock.mock.calls[2][1].body)).toEqual({
      gene: "BRAF",
      species: "human",
      limit: 3,
      year_from: 2020,
      year_to: 2025,
      cancer_keyword: "melanoma",
      sort: "relevance",
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

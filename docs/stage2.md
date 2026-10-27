# 2단계: 검색 정합성 및 FastAPI

## 실행

Python 3.12 Conda 환경에서 프로젝트 루트를 작업 디렉터리로 사용한다.
이메일과 선택적 API 키는 로컬 `.env` 또는 환경변수로만 제공한다.

```bash
conda activate canine-evidence
python -m pip install -e '.[dev]'
uvicorn canine_evidence.api:app --host 127.0.0.1 --port 8000
```

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"gene":"BRAF","species":"dog","limit":3}'
```

`/docs`에서 API를 확인하고 `/openapi.json`에서 계약을 조회한다.
저장된 계약은 `docs/openapi.json`, 실제 HTTP 응답은
`docs/stage2-response-example.json`에 있다. CLI도 동일 검색 함수를 호출한다.

## 요청·응답 계약

- gene: 앞뒤 공백 제거 후 1–200자, 영문·숫자·공백·하이픈·슬래시.
- species: dog/cat/human/all, 기본 all. CLI의 기본 종은 기존대로 dog.
- year_from/year_to: 선택, 1800–현재 UTC 연도. 역전된 범위 거절.
- cancer_keyword: 선택, 최대 200자. 검색 문법 특수문자 거절.
- limit: 1–200, 기본 20. 선언되지 않은 요청 필드 거절.
- total_count: ESearch의 전체 검색 건수. returned_count: 파싱·중복 제거 후
  실제 반환된 논문 수. 서로 같은 값이라고 가정하지 않는다.
- searched_at: 검색 흐름 시작 시각(UTC). esearch_retrieved_at 및 각 논문의
  ncbi_retrieved_at과 구분한다.
- failed_pmids, failed_count, failures: 미반환 PMID 목록·건수·원인 유형.
  성공 PMID와 실패 PMID는 겹치지 않는다.
- is_partial: 정상 논문과 실패 항목이 모두 있을 때만 true.
- from_cache: 이 단계에서는 항상 false. 영속 저장은 하지 않는다.
- 정상 0건: HTTP 200, articles=[], message="설정한 조건에서 검색된 연구 없음".

모든 Article은 unverified/low를 유지한다. 중복 PMID는 첫 번째 객체만 유지하며
서로 다른 PMID에 동일 non-null DOI가 있으면 두 논문을 보존하고 경고한다.
중복 제거 후 출판연도 내림차순으로 안정 정렬한다. 연도 누락은 마지막에 둔다.
같은 연도 내에서는 입력 순서를 유지한다.

## 오류 처리

| 상황 | HTTP | error_type |
| --- | --- | --- |
| 입력 검증 실패 | 422 | validation_error |
| ESearch 타임아웃 / 네트워크 / 429 재시도 소진 | 503 | timeout / network_error / rate_limit |
| ESearch 5xx 재시도 소진 | 502 | server_error |
| ESearch 오류 본문·잘못된 응답 | 502 | upstream_response_error |
| EFetch 일부 논문 성공 | 200 | 성공 응답의 is_partial=true와 failures |
| EFetch 전체 실패: 모든 원인이 타임아웃·네트워크·429 | 503 | efetch_all_failed |
| EFetch 전체 실패: 5xx·파싱·누락 등 포함 | 502 | efetch_all_failed |
| 내부 처리 오류 | 500 | internal_error |

전체 EFetch 실패에도 failures에 원인 유형을 보존한다. 혼합 실패는 502가
우선한다. 파싱 실패 배치는 제외하되 다른 배치의 정상 논문은 반환한다.
지원하지 않는 레코드나 누락 레코드는 요청 PMID 대조를 통해 실패에 포함한다.
요청하지 않은 PMID는 제외한다. 오류 응답은 원본 예외·요청 본문을 노출하지 않는다.

## 구조와 design.md 차이

1. SearchService 책임은 `search_service.search(request, client)` 함수로 구현했다.
   상태 없는 Deduplicator도 `deduplication.deduplicate()` 함수다. 별도의
   Service/Impl, Repository, DTO 변환 계층은 없다.
2. API lifespan에서 프로세스당 NCBIClient 하나를 생성·공유·종료한다.
   함수는 클라이언트를 인자로 받으므로 HTTP 연결 수명과 검색 로직을 분리한다.
   이는 [FastAPI lifespan 방식](https://fastapi.tiangolo.com/advanced/events/)을 따른다.
3. 설계의 SearchResponse 필드에 query_translation, esearch_retrieved_at,
   failed_count, failures, warnings, message를 추가했다. Pydantic으로 건수·PMID
   고유성·부분 성공 조건을 검증한다.
4. 외부 XML 파싱 실패를 설계의 내부 오류 500 대신 upstream 실패 502로 구분한다.
   전체 배치 실패의 502/503 충돌은 원인별 규칙으로 처리한다.
5. 입력 422도 ErrorResponse 형식을 사용하고 입력 본문을 되돌려주지 않는다.
6. 캐시, UI, AI, 종 확정 로직은 구현하지 않았다. 종 상태는 계속 unverified다.
7. 기존 requirements.md/design.md/tasks.md는 이번 작업에서 변경하지 않았다.

## 검증 (2026-10-27 UTC)

```bash
NCBI_LIVE_TEST=0 python -m pytest -q
NCBI_LIVE_TEST=1 python -m pytest -m live_api -q -s
```

- 기본 전체 테스트: 105 passed, 4 skipped (live 기본 제외).
- 별도 live 테스트: 4 passed, 105 deselected (CLI 2개 + FastAPI 2개).
- 실제 Uvicorn을 띄워 HTTP POST /search → NCBI 호출 → HTTP 200 확인 후 종료.
- BRAF: total_count=93, 반환 PMID 42775191/42847792/42680778.
- TP53: total_count=84, 반환 PMID 42580051/42930160/42018306.
- 실패 시나리오는 실제 fixture 기반 respx Mock과 서비스 테스트로 검증했다.
  실제 NCBI에 장애를 유발하지 않았다. 변형 데이터는 테스트 내부에서만 사용한다.

호출 제한은 프로세스 내 공유 클라이언트에 적용된다. 여러 worker나 별도 CLI의
합산 호출 제한은 아직 없다. 단일 worker로 실행한다. 검색 전체의 시간 제한은
별도로 없으며 httpx의 네트워크 작업 타임아웃과 제한된 재시도를 적용한다.
전문적인 종 분류나 검색 정확도 평가는 이 단계의 완료 범위가 아니다.

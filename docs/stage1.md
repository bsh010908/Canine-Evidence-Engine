# 1단계: 실제 PubMed 검색·XML 파싱

## 실제 검증 결과 (2026-10-27 UTC)

프로젝트 루트 `.env`를 읽어 실제 ESearch·EFetch 호출을 완료했다.
이메일·API 키는 문서나 fixture에 기록하지 않았다.

| 검색식 | 전체 검색 건수 | 수집한 PMID |
| --- | ---: | --- |
| `"BRAF"[tiab] AND Dogs[MeSH Terms]` | 93 | 42775191, 42847792, 42680778 |
| `"TP53"[tiab] AND Dogs[MeSH Terms]` | 84 | 42580051, 42930160, 42018306 |

수집 시각은 `tests/fixtures/pubmed/provenance.json`에 기록되어 있다.
각 검색의 첫 3건을 검증했으며 전체 검색 결과를 검증한 것은 아니다.
6건 모두 초록과 MeSH를 포함했고, PMID 42775191의 DOI는 원본에 없어 null로
유지했다. 모든 종 상태는 unverified다.

- 기본 전체 pytest: **68 passed, 2 skipped** (live API 기본 제외).
- 별도 live API pytest: **2 passed, 68 deselected**.
- XML의 PMID·제목·DOI·저널·연도·저자·초록·MeSH·Publication Type 매핑 테스트 통과.
- 연락처 메타데이터 제외 전후 Article 동일성 확인, fixture 5개 인증정보·이메일 검사 통과.
- 지원하지 않는 레코드와 정상 논문이 섞인 경우 정상 논문 보존 및 부분 실패 표시 테스트 통과.

이로써 1단계 검증을 마쳤으며, 서버·UI·캐시·종 분류 확장 단계는 진행하지 않았다.

## Python 코드 구조 원칙

하나의 프로젝트 루트와 Git 저장소를 사용한다. 백엔드는
`src/canine_evidence/` 아래에 두고, 향후 Streamlit은 `frontend/`에 둔다.
이번 단계에는 프론트엔드 파일을 생성하지 않는다.

기존 design.md와 달라지는 구현 구조:

- `PubMedParser` 클래스 대신 상태 없는 `parse_efetch_xml()` 함수를 사용한다.
- `services/query_builder.py` 대신 `query_builder.py`에 검색식 함수를 둔다.
- HTTP 연결·속도 제한 상태가 있는 `NCBIClient`, `RateLimiter`만 해당 책임의
  클래스로 유지한다. 결과 묶음과 설정은 표준 dataclass를 사용한다.
- SearchRequest와 Article은 입력·출력 검증용 Pydantic 모델이다. 별도의
  DTO 변환 계층, Interface/Impl, Service/Repository 계층을 추가하지 않는다.
- 기존 `ui/` 계획은 향후 `frontend/`로 대체한다. FastAPI, Streamlit,
  SQLAlchemy 기술 선택은 유지하되 이번 단계에는 구현하지 않는다.

작은 로직은 함수 중심으로 작성하고, 타입 힌트와 표준 라이브러리를 우선한다.
NCBI 호출, XML 파싱, 검색식 작성의 책임을 분리하되 기능 하나마다 새 계층을
만들지 않는다. 향후 종 분류·캐시·검색 흐름도 실제 기능이 생길 때 구성한다.
가독성·유지보수성·테스트 용이성을 코드 길이보다 우선하며 pytest와 필요한
외부 API Mock 테스트를 사용한다. 구조 원칙은 사용자 요청에 따라 steering과
design.md에도 반영되어 있다.

## 실행

```bash
conda activate canine-evidence
python --version  # 3.12.x
python -m pip install -e '.[dev]'
cp .env.example .env
# .env에 본인의 NCBI_EMAIL 설정. NCBI_API_KEY는 선택.
canine-pubmed BRAF --species dog --limit 3
canine-pubmed TP53 --species dog --limit 3
python -m pytest -q
NCBI_LIVE_TEST=1 python -m pytest -m live_api -s -q
```

새 환경은 `conda env create -f environment.yml`로 생성한다.
`.env`는 현재 작업 디렉터리에서만 읽으며 셸 환경변수가 우선한다.
이메일·키는 출력하지 않는다. HTTP 요청 로그의 email/api_key 매개변수는
마스킹한다. HTTP 디버그 로깅은 불필요하게 활성화하지 않는다.
`.env`는 Git 제외 대상이다.

실제 응답 fixture 재수집:

```bash
python scripts/capture_pubmed.py --output tests/fixtures/pubmed
```

수집 스크립트는 ESearch JSON, EFetch XML, 검색식·PMID·수집 시각을 보존하도록
구현되어 있다. 실제 fixture 생성 여부는 `tests/fixtures/pubmed/`에서 확인한다.
기존 fixture를 갱신하므로 변경 내역과 PMID를 검토한다. 원본 응답에는
임의 논문 데이터를 추가하지 않는다. 오류 테스트는 원본 필드를 삭제하거나
응답을 손상시키며, 해당 결과를 실제 논문 데이터로 저장하지 않는다.

XML fixture는 원본에서 AffiliationInfo, Identifier, InvestigatorList를 제외한
검증용 사본이다. 공개 서지 정보인 저자명은 유지한다. 나머지 XML에 이메일
주소가 남아 있으면 저장을 거절한다. 제외 전후 Article 필드의 동일성을
확인하고 원본·저장본 SHA-256, 제외 항목 수를 provenance에 기록한다.
두 검색과 검증이 모두 완료된 후 파일 저장을 시작하며, 인증 정보의 원문·URL
인코딩 값이 저장 내용에 포함되면 거절한다.

## 구현 범위와 계약

- ESearch: `db=pubmed`, `retmode=json`, `sort=pub_date`, 최대 200건.
- EFetch: `db=pubmed`, `retmode=xml`, 요청당 최대 100 PMID (앱의 제한).
- 키 매개변수는 공식 명칭 `api_key`; 모든 요청에 `tool`, `email` 사용.
- 공유 클라이언트 내 요청 시작 간격을 제한: 키 없으면 3회/s, 있으면 10회/s.
  재시도도 같은 제한을 따른다. 여러 클라이언트·프로세스·동일 IP의 다른 앱을
  합산하는 분산 제한기는 이 단계에 없다. CLI는 순차 실행한다.
- HTTP 429는 1/2/4초 대기 후 최대 3회 재시도; 숫자 Retry-After가 더 길면 존중.
  HTTP 5xx는 1/2초 대기 후 최대 2회 재시도. 네트워크·타임아웃은 즉시 오류.
- 기본 30초는 httpx의 각 네트워크 작업 타임아웃이다. 재시도를 포함한 검색
  전체의 30초 제한을 의미하지 않는다.
- ESearch 응답 본문의 오류, 잘못된 JSON/XML, 잘못된 구조는 정상 0건으로
  처리하지 않는다. EFetch 요청 PMID와 파싱 결과를 대조한다.
- CLI는 성공 시 0, 전체 실패 시 1, 일부 레코드 실패 시 2로 종료한다.
  부분 결과에는 실패 PMID와 원인 유형을 포함한다.
- 원본 수신 시각을 파서에 전달하여 UTC `ncbi_retrieved_at`에 기록한다.
- 모든 종 상태는 `unverified`; 종 분류 로직은 구현하지 않는다.
- SQLite, FastAPI 서버, Streamlit, AI 요약, 중복 제거 서비스는 구현하지 않는다.

## 기존 문서와의 차이 및 한계

1. Conda/Python 3.12 사용. `venv` 예시는 변경하지 않았다.
2. 가상 PMID fixture 대신 실제 응답과 provenance를 보존한다.
3. `pmid` 없는/유효하지 않은 레코드는 파싱 시 경고 후 제외한다. 유효 Article은
   PMID 필수이며 저자 누락은 빈 목록이다.
4. 특수 검색 문자는 임의 백슬래시 이스케이프 대신 입력 검증에서 거절한다.
   생략된 연도 경계는 1800/현재 UTC 연도다.
5. 논문의 구조화 초록·내부 XML 태그·단체 저자·이니셜을 처리한다. 출판연도는
   JournalIssue/PubDate/Year에서만 읽고 MedlineDate나 전자 출판일로 추론하지 않는다.
6. MeSH Descriptor만 보존하며 qualifier 기반 종 확정은 수행하지 않는다.
7. `PubmedArticle`만 지원한다. `PubmedBookArticle` 등은 제외 건수를 경고하고
   같은 배치의 정상 논문은 보존한다. 지원 가능한 레코드가 하나도 없으면
   파싱 오류로 보고한다. CLI는 요청 PMID 중 반환되지 않은 항목을 부분 실패로
   표시한다. 잘못된 XML이나 정상 논문의 필수 구조 누락은 여전히 오류다.
8. `[Gene Name]`가 반드시 0건을 반환한다는 live 테스트는 추가하지 않는다.
9. 최소 설정에는 표준 dataclass와 python-dotenv를 사용한다. pydantic-settings,
   Hypothesis, 서버·DB·UI 의존성은 이 단계에 필요하지 않아 설치하지 않는다.
10. MeSH 종 필터는 미색인 문헌을 놓칠 수 있고, 검색 결과는 임상 결론이 아니다.

공식 사양:
- https://www.ncbi.nlm.nih.gov/sites/books/NBK25499/
- https://www.ncbi.nlm.nih.gov/books/NBK25497/
- https://pubmed.ncbi.nlm.nih.gov/help/

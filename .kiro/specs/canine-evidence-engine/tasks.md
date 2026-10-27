# Implementation Plan: Canine Evidence Engine

## Overview

Python 기반 반려동물 유전자·변이 연구 검색 서비스를 구현한다. 프로젝트 환경 설정부터 시작하여 데이터 모델, 외부 API 클라이언트, 파싱·분류·중복 제거 컴포넌트, 서비스 레이어, FastAPI 백엔드, Streamlit UI, 테스트 순서로 점진적으로 구축한다. 각 단계는 이전 단계의 결과물을 기반으로 하며, 고아 코드 없이 최종적으로 완전히 연결된 시스템을 완성한다.

## Tasks

- [ ] 1. 프로젝트 환경 설정
  - [ ] 1.1 디렉터리 구조 및 패키지 초기화
    - `src/canine_evidence/`, `clients/`, `parsers/`, `services/`, `classifiers/`, `deduplicator/`, `storage/`, `models/`, `ui/`, `tests/fixtures/` 디렉터리와 `__init__.py` 파일 생성
    - `pyproject.toml` 작성: Python 3.12, FastAPI, Streamlit, SQLAlchemy, httpx, pydantic, hypothesis, pytest, pytest-asyncio, respx 의존성 포함
    - `.env.example` 작성: `NCBI_EMAIL`, `NCBI_API_KEY`, `OPENAI_API_KEY`, `ENABLE_AI_SUMMARY`, `DATABASE_URL` 항목 포함 (실제 값 없이 키만 명시)
    - `src/canine_evidence/config.py` 작성: 환경변수를 로드하는 `Settings` 클래스 구현 (pydantic-settings 사용)
    - `.gitignore`에 `.env`, `*.db`, `__pycache__/`, `.pytest_cache/` 추가
    - _Requirements: 6.2, 7.3_

- [ ] 2. Pydantic 데이터 모델
  - [ ] 2.1 Article 및 열거형 모델 구현
    - `src/canine_evidence/models/article.py`에 `SpeciesStatus`, `SpeciesEvidenceStrength` Enum 구현
    - `Article` Pydantic 모델 구현: pmid, doi, title, abstract, abstract_available, authors, publication_year, journal, source_url, ncbi_retrieved_at, mesh_terms, publication_types, species_status, species_evidence_strength, species_evidence_notes 필드 포함
    - _Requirements: 2.1, 2.2, 2.3, 4.7_

  - [ ] 2.2 SearchRequest 및 SearchResponse 모델 구현
    - `src/canine_evidence/models/search.py`에 `SearchRequest` 구현: gene(max_length=200), species, year_from, year_to, cancer_keyword, limit(1–200) 필드 포함
    - `SearchResponse` 구현: articles, total_count, returned_count, searched_at, query_string, is_partial, failed_pmids, from_cache 필드 포함
    - _Requirements: 1.1, 1.4, 1.5, 6.5_

- [ ] 3. SQLAlchemy ORM 모델 및 SQLite 초기화
  - [ ] 3.1 ORM 모델 및 CRUD 구현
    - `src/canine_evidence/storage/sqlite.py`에 `ArticleORM`, `SearchCacheORM`, `SearchCacheArticleORM` SQLAlchemy 모델 구현
    - `ArticleORM`: pmid(PK), doi, title, abstract, abstract_available, authors_json, publication_year, journal, source_url, ncbi_retrieved_at, mesh_terms_json, publication_types_json, species_status, species_evidence_strength, species_evidence_notes_json 컬럼 포함
    - `SearchCacheORM`: cache_key(PK), gene, species, year_from, year_to, cancer_keyword, limit, cached_at, total_count, returned_count, query_string 컬럼 포함
    - `SearchCacheArticleORM`: cache_key(FK), pmid(FK), sort_order 컬럼으로 복합 PK 구성
    - DB 초기화 함수(`init_db`), Article 저장·조회, 캐시 저장·조회·TTL 판단(24시간) 함수 구현
    - PMID가 null인 Article은 저장 대상에서 제외하는 로직 포함
    - SQLite 저장 오류 발생 시 로그 기록 후 검색 결과 반환에 영향 없도록 처리
    - _Requirements: 7.1, 7.2, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 3.2 SQLite 캐시 단위 테스트 작성
    - `tests/test_cache.py` 작성: 캐시 저장·조회·TTL 만료 시나리오 테스트
    - PMID null Article 저장 제외 검증
    - 동일 PMID 중복 저장 방지 검증
    - _Requirements: 7.4, 7.5_

- [ ] 4. NCBI_Client 구현
  - [ ] 4.1 ESearch 및 EFetch 구현
    - `src/canine_evidence/clients/ncbi.py`에 `NCBIClient` 클래스 구현
    - `esearch()`: NCBI ESearch API 호출, PMID 목록과 total_count 반환
    - `efetch_batch()`: PMID 목록을 100개 단위 배치로 EFetch 호출, 성공 XML 목록과 failed_pmids 반환
    - 모든 API 호출에 타임아웃(기본 30초) 적용
    - `NCBITimeoutError`, `NCBIRateLimitError`, `NCBIServerError` 커스텀 예외 클래스 정의
    - _Requirements: 1.2, 1.3, 6.1, 6.2_

  - [ ] 4.2 속도 제한 및 재시도 로직 구현
    - `asyncio` 기반 토큰 버킷으로 속도 제한 구현: API 키 없으면 3 req/s, 있으면 10 req/s
    - HTTP 429 응답 시 지수 백오프(1s → 2s → 4s) 최대 3회 재시도 후 `NCBIRateLimitError` 발생
    - HTTP 5xx 응답 시 최대 2회 재시도 후 `NCBIServerError` 발생
    - 재시도 중에도 속도 제한 유지
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 4.3 NCBI_Client Mock 기반 테스트 작성
    - `tests/test_ncbi_client.py` 작성: `respx`로 NCBI API Mock 처리
    - 429 응답 → 지수 백오프 재시도 3회 후 `NCBIRateLimitError` 발생 검증
    - 5xx 응답 → 최대 2회 재시도 후 `NCBIServerError` 발생 검증
    - 타임아웃 → `NCBITimeoutError` 발생 검증
    - 속도 제한: API 키 없을 때 3 req/s 초과 방지 검증
    - _Requirements: 6.2, 6.3, 6.4_

- [ ] 5. PubMed_Parser 구현
  - [ ] 5.1 XML 파싱 및 Article 변환 구현
    - `src/canine_evidence/parsers/pubmed_xml.py`에 `PubMedParser` 클래스 구현
    - `parse_efetch_xml(xml_text)`: NCBI EFetch XML을 파싱하여 `Article` 객체 목록 반환
    - 필드 매핑: pmid(`<PMID>`), doi(`<ArticleId IdType="doi">`), title(`<ArticleTitle>`), abstract(`<AbstractText>`), authors(`<AuthorList>`), publication_year(`<PubDate><Year>`), journal(`<Journal><Title>`), mesh_terms(`<MeshHeadingList>`의 `<DescriptorName>`), publication_types(`<PublicationTypeList>`의 `<PublicationType>`)
    - source_url: `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` 형식 (pmid가 null이면 null)
    - ncbi_retrieved_at: 파서 호출 시각 (UTC ISO 8601)
    - abstract 없으면 `abstract=null`, `abstract_available=False`
    - PMID 없는 항목은 결과에서 제외하고 경고 로그 기록
    - 파싱 불가 XML은 `ParseError` 발생 (Article 미생성)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 6.6_

  - [ ] 5.2 XML Fixture 파일 생성
    - `tests/fixtures/sample_efetch_with_mesh.xml`: MeSH 용어·Publication Type 포함 샘플
    - `tests/fixtures/sample_efetch_no_abstract.xml`: 초록 없는 샘플 (abstract_available=false)
    - `tests/fixtures/sample_efetch_no_doi.xml`: DOI 없는 샘플
    - `tests/fixtures/sample_efetch_no_mesh.xml`: MeSH 없는 샘플 (unverified 경로)
    - `tests/fixtures/sample_efetch_invalid.xml`: 파싱 불가 샘플
    - 모든 fixture는 실제 NCBI EFetch XML 구조를 따르되 가상의 PMID 사용
    - _Requirements: 2.1, 2.2, 2.7_

  - [ ]* 5.3 PubMed_Parser 단위 테스트 작성
    - `tests/test_pubmed_parser.py` 작성: 각 fixture 파일 기반 파싱 결과 검증
    - 정상 XML에서 모든 필드(PMID, DOI, title, abstract, authors, publication_year, journal, source_url, ncbi_retrieved_at, mesh_terms, publication_types)가 올바르게 파싱됨 검증
    - MeSH 없는 XML에서 mesh_terms=[], publication_types=[] 검증
    - 초록 없는 경우 abstract=null, abstract_available=False 검증
    - PMID 없는 항목이 결과에서 제외됨 검증
    - 파싱 불가 XML에서 ParseError 발생 검증
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_

  - [ ]* 5.4 Property 테스트 작성 - Article 직렬화 라운드 트립 (Property 1)
    - **Property 1: Article 직렬화 라운드 트립**
    - **Validates: Requirements 2.6**
    - `tests/test_pubmed_parser.py`에 Hypothesis `article_strategy()` 구현: mesh_terms, publication_types 포함한 임의 Article 생성
    - Article JSON 직렬화 후 역직렬화하면 모든 필드(PMID, DOI, title, abstract, abstract_available, authors, publication_year, journal, source_url, ncbi_retrieved_at, mesh_terms, publication_types)가 원본과 동일한지 검증
    - _Requirements: 2.6_

  - [ ]* 5.5 Property 테스트 작성 - source_url 형식 불변성 (Property 6)
    - **Property 6: source_url 형식 불변성**
    - **Validates: Requirements 2.5, 8.4**
    - `tests/test_pubmed_parser.py`에 임의 PMID 문자열(`st.text()`)로 source_url 생성 결과 검증
    - non-null PMID → source_url이 `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` 형식을 따르는지 검증
    - null PMID → source_url도 null인지 검증
    - _Requirements: 2.5, 8.4_

- [ ] 6. Deduplicator 구현
  - [ ] 6.1 PMID 기반 중복 제거 구현
    - `src/canine_evidence/deduplicator/deduplicator.py`에 `Deduplicator` 클래스 구현
    - `deduplicate(articles)`: `DeduplicationResult` 반환 (`articles`, `removed_count`, `warnings` 포함)
    - PMID null 항목: 결과 제외, 경고 로그 기록
    - 동일 PMID: 첫 번째 항목 유지, 나머지 제거
    - 다른 PMID + 같은 non-null DOI: 둘 다 포함, 경고 로그 기록
    - 결과 목록 내 모든 PMID는 non-null 및 고유함 보장
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 6.2 Deduplicator 단위 테스트 작성
    - `tests/test_deduplicator.py` 작성
    - PMID 중복 시 첫 번째 항목 유지 검증
    - PMID null 항목 제외 및 경고 로그 기록 검증
    - 다른 PMID + 같은 DOI → 둘 다 포함 + 경고 로그 검증
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 6.3 Property 테스트 작성 - 중복 제거 멱등성 (Property 2)
    - **Property 2: 중복 제거 멱등성**
    - **Validates: Requirements 3.5**
    - `tests/test_deduplicator.py`에 `st.lists(article_strategy(), max_size=50)` 전략 사용
    - Deduplicator를 두 번 연속 적용하면 두 번째 결과가 첫 번째 결과와 동일한 PMID 순서와 내용인지 검증
    - _Requirements: 3.5_

  - [ ]* 6.4 Property 테스트 작성 - PMID 고유성 보장 (Property 3)
    - **Property 3: 중복 제거 후 PMID 고유성 보장**
    - **Validates: Requirements 3.4**
    - `tests/test_deduplicator.py`에 `article_with_nulls_strategy()` 구현: PMID null 항목 포함 가능
    - Deduplicator 적용 결과 목록에서 모든 PMID가 non-null이고 고유한지 검증
    - _Requirements: 3.4_

- [ ] 7. Species_Classifier 구현
  - [ ] 7.1 종 분류 로직 구현
    - `src/canine_evidence/classifiers/species_classifier.py`에 `SpeciesClassifier` 클래스 구현
    - `classify(article)`: `SpeciesClassification` 반환 (`status`, `evidence_strength`, `evidence_notes` 포함)
    - 1차 근거: mesh_terms + publication_types (구조화된 메타데이터). Evidence strength: `high`
    - 2차 근거: title 키워드. Evidence strength: `medium`
    - 3차 근거: abstract 키워드. Evidence strength: `low`, 항상 `unverified`
    - `confirmed` 부여 조건: (a) 해당 종이 실험 대상임을 나타내는 근거 존재 AND (b) 다른 종이 실험 대상임을 나타내는 상충 근거 없음
    - MeSH에 "Dogs"만 포함된 경우 확정 근거 불충분 → `unverified`
    - MeSH "Dogs" + publication_types "Animal Study" → 실험 대상 근거로 사용 가능
    - 단순 언급("compared to dogs", "unlike canine models")은 실험 대상 근거로 사용하지 않음
    - 상충 근거 존재 시 `unverified`로 설정하고 evidence_notes에 상충 사실 기록
    - 복수 종이 실험 대상으로 확인되면 `multi_species`
    - mesh_terms, publication_types, title, abstract 모두 없으면 `unverified`, `low`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 7.2 Species_Classifier 단위 테스트 작성
    - `tests/test_species_classifier.py` 작성
    - mesh_terms ["Dogs"]만 있고 publication_types 없음 → `unverified`, `high` 검증
    - mesh_terms ["Dogs"] + publication_types ["Animal Study"] → `dog_confirmed`, `high` 검증
    - 제목에 "canine" 포함, mesh_terms 없음 → `medium` 증거 강도 검증
    - 초록에만 "dog" 언급 → `unverified`, `low` 검증
    - mesh_terms ["Humans"], 제목에 "canine" 포함 → `unverified`, 상충 기록 검증
    - mesh_terms, publication_types, title, abstract 모두 null/empty → `unverified`, `low` 검증
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.8_

  - [ ]* 7.3 Property 테스트 작성 - 상충 시 unverified 보장 (Property 4)
    - **Property 4: 종 분류 상충 시 unverified 보장**
    - **Validates: Requirements 4.5**
    - `tests/test_species_classifier.py`에 `conflicting_article_strategy()` 구현: mesh_terms와 title이 서로 다른 종을 가리키는 Article 생성
    - Species_Classifier가 반드시 `unverified`를 반환하고 evidence_notes에 상충 사실이 기록되는지 검증
    - _Requirements: 4.5_

  - [ ]* 7.4 Property 테스트 작성 - 분류 근거 보존 (Property 5)
    - **Property 5: 분류 근거 보존**
    - **Validates: Requirements 4.7**
    - `tests/test_species_classifier.py`에 `article_with_metadata_strategy()` 구현: mesh_terms 또는 title이 non-empty인 Article 생성
    - 분류 결과의 evidence_notes에 분류 판단에 사용된 MeSH 용어 또는 키워드가 1개 이상 포함되는지 검증
    - _Requirements: 4.7_

- [ ] 8. build_query 검색식 구성 구현
  - [ ] 8.1 PubMed 검색식 빌더 구현
    - `src/canine_evidence/services/query_builder.py`에 `build_query(request: SearchRequest) -> str` 함수 구현
    - 유전자명은 `[tiab]` 태그 사용 (`[Gene Name]` 태그 사용 금지)
    - species="dog" → `Dogs[MeSH Terms]` 추가, species="cat" → `Cats[MeSH Terms]` 추가, species="human" → `Humans[MeSH Terms]` 추가, species="all" → 종 필터 없음
    - cancer_keyword 있으면 `"keyword"[tiab]` 추가
    - year_from/year_to 있으면 `year_from:year_to[pdat]` 추가
    - gene에 특수문자(`"`, `[`, `]`, `(`, `)`) 포함 시 검색식에서 이스케이프 처리
    - year_from > year_to 인 경우 ValueError 발생 (FastAPI에서 422로 매핑)
    - _Requirements: 1.1, 1.2, 8.1_

  - [ ]* 8.2 build_query 단위 테스트 작성
    - `tests/test_query_builder.py` 작성
    - `gene="BRAF"`, `species="dog"` → `'"BRAF"[tiab] AND Dogs[MeSH Terms]'` 검증
    - `gene="TP53"`, `species="all"` → `'"TP53"[tiab]'` 검증 (종 필터 없음)
    - cancer_keyword 포함 시 `[tiab]` 태그로 추가됨 검증
    - year_from/year_to 포함 시 `[pdat]` 범위 포함됨 검증
    - gene에 특수문자 포함 시 이스케이프 처리 검증
    - `[Gene Name]` 태그가 생성된 검색식에 포함되지 않음 검증
    - _Requirements: 1.2_

- [ ] 9. Checkpoint - 핵심 컴포넌트 완성
  - 9.1 단계까지 완성된 컴포넌트의 모든 단위 테스트가 통과하는지 확인한다. 문제가 있으면 사용자에게 보고한다.

- [ ] 10. Search_Service 구현
  - [ ] 10.1 캐시 조회 및 NCBI 호출 오케스트레이션 구현
    - `src/canine_evidence/services/search_service.py`에 `SearchService` 클래스 구현
    - Cache_Key 생성: gene(strip().upper()), species, year_from, year_to, cancer_keyword(strip().lower()), limit을 SHA-256 해시로 정규화
    - 캐시 HIT + TTL 24시간 이내: SQLite_Cache에서 결과 반환, searched_at을 현재 시각으로 설정
    - 캐시 MISS: NCBI_Client.esearch → EFetch 배치 → PubMed_Parser → Deduplicator → Species_Classifier 순서로 처리
    - EFetch 배치 실패 분류: 1개 이상 성공 → `is_partial=true`(200), 모든 배치 실패 → 전체 실패(502/503)
    - is_partial=false 경우에만 SQLite_Cache 저장 (저장 오류는 로그 기록 후 무시)
    - 검색 결과를 출판연도 내림차순으로 정렬하여 반환
    - searched_at을 현재 요청 시각(UTC)으로 설정 (캐시 반환 시에도 현재 시각 사용)
    - _Requirements: 1.2, 1.3, 1.4, 1.6, 1.7, 6.5, 7.1, 7.2, 7.3, 7.7, 8.1_

  - [ ]* 10.2 Search_Service Mock 기반 통합 테스트 작성
    - `tests/test_search_service.py` 작성: NCBI_Client, SQLite_Cache를 Mock 처리
    - 캐시 HIT 시 외부 API 미호출 검증
    - 캐시 MISS → API 호출 → 캐시 저장 흐름 검증
    - limit=200, 배치 2회 중 2번째 실패 → `is_partial=true`, `failed_pmids` 포함, 캐시 저장 생략 검증
    - limit=200, 배치 2회 모두 실패 → 전체 실패 응답 검증
    - is_partial=false → 캐시 저장 호출됨 검증
    - 검색 결과 0건 → 빈 Article 목록과 "설정한 조건에서 검색된 연구 없음" 응답 검증
    - _Requirements: 1.6, 1.7, 6.5, 7.2, 7.7_

  - [ ]* 10.3 Property 테스트 작성 - 캐시 키 결정론적 생성 (Property 7)
    - **Property 7: 캐시 키 결정론적 생성**
    - **Validates: Requirements 7.1**
    - `tests/test_cache.py`에 `search_request_strategy()` 구현: 임의 SearchRequest 생성
    - 동일한 SearchRequest에 make_cache_key를 여러 번 호출하면 항상 동일한 Cache_Key 반환 검증
    - gene 대소문자가 다르거나 cancer_keyword 앞뒤 공백이 다른 두 SearchRequest가 정규화 후 동일하면 동일한 Cache_Key 반환 검증
    - _Requirements: 7.1_

- [ ] 11. FastAPI 라우터 구현
  - [ ] 11.1 FastAPI 서버 및 라우터 구현
    - `src/canine_evidence/api.py`에 FastAPI 앱과 `POST /search` 라우터 구현
    - `SearchRequest` Pydantic 모델로 입력 검증: gene 빈 값 또는 200자 초과 시 HTTP 422 자동 반환
    - HTTP 오류 매핑: `NCBITimeoutError`/`NCBIRateLimitError` → 503, `NCBIServerError`/모든 EFetch 배치 실패 → 502, 내부 오류 → 500
    - 오류 응답 구조: `{"detail": "...", "error_type": "timeout|rate_limit|server_error|parse_error|efetch_all_failed"}`
    - FastAPI 앱 진입점(`main.py` 또는 `api.py`) 구성
    - _Requirements: 1.5, 6.7, 6.8_

  - [ ]* 11.2 FastAPI 통합 테스트 작성
    - `tests/test_api.py` 작성: `httpx.AsyncClient`로 TestClient 구성, Search_Service Mock 처리
    - 정상 검색 요청 → 200 및 SearchResponse 구조 검증
    - gene 빈 값 → 422 반환 검증
    - gene 200자 초과 → 422 반환 검증
    - NCBITimeoutError → 503 반환 및 error_type="timeout" 검증
    - NCBIServerError → 502 반환 및 error_type="server_error" 검증
    - _Requirements: 1.5, 6.7, 6.8_

- [ ] 12. Streamlit UI 구현
  - [ ] 12.1 검색 폼 및 결과 화면 구현
    - `ui/app.py`에 Streamlit UI 구현
    - 검색 폼: 유전자명(필수), 종(dog/cat/human/all, 필수), 연도 범위(year_from/year_to, 필수), 암종 키워드(선택), 검색 버튼
    - 검색 결과 메타: "검색 기준: NCBI PubMed | 검색 시각: {searched_at(UTC ISO 8601)}", 전체 검색 건수(total_count), 표시 건수(returned_count) 표시
    - 종 그룹별 섹션 헤더: `dog_confirmed` / `cat_confirmed` / `human_confirmed` / `multi_species` / `unverified` 순서로 그룹 구분
    - 논문 카드: 제목, 출판연도, 저널, PMID, Species_Status, 초록 유무(`abstract_available=false` 시 "초록 없음"), PubMed 원문 링크(새 탭), ncbi_retrieved_at 표시
    - Species_Status가 `unverified`인 논문 카드에 "종 미확인" 레이블 표시
    - 검색 결과 0건 → "설정한 조건에서 검색된 연구 없음" 메시지 표시
    - _Requirements: 4.9, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.3, 8.2_

  - [ ] 12.2 오류 처리 및 부분 성공 표시 구현
    - HTTP 503 → "NCBI API에 일시적으로 연결할 수 없습니다. 잠시 후 재시도해 주세요." 표시
    - HTTP 502 → "NCBI 서버 오류가 발생했습니다. 잠시 후 재시도해 주세요." 표시
    - is_partial=true → "일부 논문 데이터를 불러오지 못했습니다. (실패 PMID: N건)" 표시
    - 오류 발생 시 이전 검색 조건 값 유지 (Streamlit session_state 활용)
    - 정상 처리 후 0건과 오류로 인한 0건을 다른 메시지로 구분하여 표시
    - _Requirements: 5.7, 5.8, 6.9_

- [ ] 13. Checkpoint - 전체 통합 완성
  - 13.1 모든 컴포넌트가 Search_Service를 통해 연결되어 있는지 확인한다. FastAPI 서버와 Streamlit UI가 연동되는지 확인한다. 모든 단위 테스트와 통합 테스트가 통과하는지 확인한다. 문제가 있으면 사용자에게 보고한다.

- [ ] 14. Live API 테스트 작성
  - [ ] 14.1 NCBI Live API 통합 테스트 작성
    - `tests/test_ncbi_client.py`에 `@pytest.mark.live_api` 마크된 테스트 추가
    - `NCBI_LIVE_TEST=1` 환경변수가 설정된 경우에만 실행되도록 `pytest.ini` 또는 `conftest.py`에 마크 조건 설정
    - `BRAF + Dogs MeSH` 검색이 실제 PubMed에서 1건 이상 반환하는지 검증
    - `TP53 + Dogs MeSH` 검색이 실제 PubMed에서 1건 이상 반환하는지 검증
    - `[Gene Name]` 태그로 검색 시 PubMed가 0건 또는 오류를 반환하는지 검증
    - _Requirements: 1.2, 8.1_

## Notes

- `*` 표시된 태스크는 선택 사항으로 MVP 빠른 완성을 위해 건너뛸 수 있다.
- 각 태스크는 특정 requirements 항목과 연결되어 있어 추적 가능하다.
- Checkpoint 태스크(9, 13)에서 테스트 통과 여부를 확인하고 문제 시 사용자에게 보고한다.
- Property 테스트는 `pytest-hypothesis`(Hypothesis)를 사용하며 최소 100 iterations로 실행된다.
- 각 Property 테스트는 `# Feature: canine-evidence-engine, Property {번호}: {property_text}` 주석으로 설계 문서와 연결한다.
- Live API 테스트(`@pytest.mark.live_api`)는 `NCBI_LIVE_TEST=1` 환경변수가 있을 때만 실행된다.
- `.env` 파일은 Git에 추가하지 않으며 API 키는 환경변수로만 관리한다.
- AI 요약 기능(P1)은 이 MVP 구현 범위에서 제외된다.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1", "8.1"] },
    { "id": 3, "tasks": ["3.2", "4.1", "8.2"] },
    { "id": 4, "tasks": ["4.2", "5.1", "5.2"] },
    { "id": 5, "tasks": ["4.3", "5.3", "5.4", "5.5", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "7.1"] },
    { "id": 7, "tasks": ["7.2", "7.3", "7.4", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "11.1"] },
    { "id": 9, "tasks": ["11.2", "12.1"] },
    { "id": 10, "tasks": ["12.2", "14.1"] }
  ]
}
```

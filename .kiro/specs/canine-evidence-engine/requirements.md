# Requirements Document

## Introduction

Canine Evidence Engine은 반려동물(초기: 개) 유전자·변이 및 종양 관련 연구 근거를 PubMed/NCBI에서 검색하고, 연구 대상 종과 출처를 명확히 구분하여 검증 가능한 형태로 제공하는 Python 기반 연구 검색 보조 서비스이다.

사용자가 유전자명(예: `BRAF`, `TP53`)과 선택적 조건(종, 기간, 암종 키워드)을 입력하면, 시스템은 NCBI E-utilities를 통해 PubMed 논문을 수집하고, 메타데이터를 정규화하여 출처가 확인된 논문 카드를 제공한다. AI 요약은 MVP(P0) 범위에서 제외하며, 진단·치료 추천 기능은 구현하지 않는다.

## Glossary

- **Search_Service**: 검색 조건을 받아 PubMed 조회를 수행하고 논문 목록을 반환하는 서비스 컴포넌트
- **NCBI_Client**: NCBI E-utilities(ESearch, EFetch, ESummary) API를 호출하는 외부 API 클라이언트
- **PubMed_Parser**: NCBI API 응답(XML/JSON)을 내부 Article 모델로 변환하는 파서
- **Article**: PMID, DOI, 제목, 초록, 저자, 출판연도, 저널, 출처 URL, NCBI 데이터 수집 시각, 종 분류 상태를 포함하는 논문 데이터 모델
- **Deduplicator**: PMID 기준으로 중복 논문을 제거하는 컴포넌트
- **Species_Classifier**: 논문의 연구 대상 종을 분류하고 불확실성 상태를 부여하는 컴포넌트
- **Search_Request**: 유전자명, 종, 기간, 암종 키워드, 결과 수 제한을 포함하는 검색 요청 모델
- **Cache_Key**: gene, species, year_from, year_to, cancer_keyword, limit 전체를 정규화하여 생성한 캐시 식별자
- **Species_Status**: 논문의 연구 대상 종 확인 상태 — `dog_confirmed`, `cat_confirmed`, `human_confirmed`, `multi_species`, `unverified` 중 하나
- **Species_Evidence_Strength**: 종 분류 증거 강도 — `high`(구조화된 메타데이터에서 해당 종이 실험 대상임을 명시), `medium`(제목에서 해당 종이 실험 대상임을 명시), `low`(초록에만 관련 키워드가 포함) 중 하나
- **ncbi_retrieved_at**: NCBI API에서 Article 데이터를 수집한 시각 (UTC ISO 8601); Article에 기록
- **cached_at**: 검색 결과를 SQLite_Cache에 저장한 시각 (UTC ISO 8601); 캐시 TTL 판단에 사용
- **searched_at**: 사용자가 현재 검색 요청을 실행한 시각 (UTC ISO 8601); 캐시 반환 시에도 현재 요청 시각으로 설정
- **SQLite_Cache**: 검색 결과와 논문 메타데이터를 로컬에 저장하는 SQLite 기반 캐시 저장소
- **Streamlit_UI**: 검색 입력, 논문 목록, 논문 카드를 표시하는 Streamlit 기반 사용자 인터페이스
- **FastAPI_Server**: 검색 요청을 처리하고 결과를 반환하는 FastAPI 기반 백엔드 서버

---

## Requirements

### Requirement 1: 유전자명 기반 PubMed 논문 검색

**User Story:** As a 연구 담당자, I want 유전자명을 입력해 관련 PubMed 논문을 검색하고 싶다, so that 특정 유전자와 연관된 연구 근거를 빠르게 파악할 수 있다.

#### Acceptance Criteria

1. WHEN Search_Request가 수신되면, THE Search_Service SHALL 유전자명(gene, 최대 200자), 종(species), 연도 범위(year_from, year_to), 선택적 암종 키워드(cancer_keyword), 결과 수 제한(limit, 1–200)을 포함하는 Search_Request를 입력으로 받아 검색을 시작한다.
2. WHEN Search_Request가 수신되면, THE Search_Service SHALL NCBI_Client를 통해 ESearch API를 호출하여 조건에 맞는 PMID 목록과 전체 검색 건수(total_count)를 조회한다.
3. WHEN ESearch 결과로 PMID 목록이 반환되면, THE NCBI_Client SHALL EFetch 또는 ESummary API를 배치로 호출하여 각 논문의 제목, 초록, 저자, 출판연도, 저널, PMID를 수집하며, DOI가 NCBI 응답에 포함된 경우에만 수집한다.
4. THE Search_Service SHALL 검색에 사용된 검색식(query string), ESearch 전체 검색 건수(total_count), 실제 반환된 논문 건수(returned_count), 사용자 검색 시각(searched_at)을 함께 저장한다.
5. IF 유전자명이 빈 문자열이거나 200자를 초과하면, THEN THE FastAPI_Server SHALL HTTP 422 상태 코드와 함께 유효성 오류 메시지를 반환한다.
6. IF 검색 결과가 0건이면, THEN THE Search_Service SHALL 빈 Article 목록과 함께 "입력한 조건에서 검색된 연구 없음"을 나타내는 응답을 반환하며, 해당 유전자에 대한 연구 자체가 존재하지 않는다는 결론을 응답에 포함하지 않는다.
7. IF NCBI_Client가 ESearch 또는 EFetch 호출 중 타임아웃(30초) 또는 복구 불가 HTTP 오류를 반환하면, THEN THE Search_Service SHALL 검색을 중단하고 실패 응답을 FastAPI_Server에 전달한다.

---

### Requirement 2: 논문 메타데이터 수집 및 정규화

**User Story:** As a 연구 담당자, I want 수집된 논문의 메타데이터가 일관된 형식으로 제공되기를 원한다, so that 논문 정보를 신뢰할 수 있고 비교하기 쉽다.

#### Acceptance Criteria

1. WHEN NCBI API로부터 응답을 수신하면, THE PubMed_Parser SHALL 응답을 파싱하여 PMID, DOI, 제목, 초록, 저자 목록, 출판연도, 저널명, PubMed 원문 URL, NCBI 데이터 수집 시각(ncbi_retrieved_at)을 포함하는 Article 객체를 생성하며, ncbi_retrieved_at은 UTC 기준 ISO 8601 형식(예: `2024-01-15T09:30:00Z`)으로 기록한다.
2. IF 초록 필드가 API 응답에 없으면, THEN THE PubMed_Parser SHALL Article의 abstract 필드를 `null`로 설정하고 `abstract_available: false`를 함께 기록한다.
3. IF DOI 필드가 API 응답에 없으면, THEN THE PubMed_Parser SHALL Article의 doi 필드를 `null`로 설정한다.
4. THE PubMed_Parser SHALL PMID, DOI, 제목, 출판연도, 저널명 필드가 NCBI 응답에 없는 경우 각각 `null`로 기록하며 임의의 값을 생성하거나 다른 필드로부터 추론하지 않는다.
5. IF PMID가 null이 아닌 값이면, THEN THE PubMed_Parser SHALL Article의 source_url을 `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` 형식으로 구성하며, PMID가 `null`인 경우 source_url도 `null`로 설정한다.
6. WHEN 유효한 NCBI API 응답을 파싱하여 Article 객체를 직렬화한 후 다시 파싱하면, THE PubMed_Parser SHALL PMID, DOI, 제목, 초록, 저자 목록, 출판연도, 저널명, source_url, ncbi_retrieved_at 모든 필드가 원본 Article 객체와 동일한 값을 가지는 Article 객체를 생성한다.
7. IF NCBI API 응답이 파싱할 수 없는 형식이거나 필수 구조가 누락된 경우, THEN THE PubMed_Parser SHALL Article 객체를 생성하지 않고 파싱 실패 오류를 반환한다.

---

### Requirement 3: PMID 기반 중복 제거

**User Story:** As a 연구 담당자, I want 동일한 논문이 중복으로 표시되지 않기를 원한다, so that 검색 결과를 신뢰하고 중복 작업을 줄일 수 있다.

#### Acceptance Criteria

1. WHEN Article 목록이 중복 제거 처리에 입력되면, THE Deduplicator SHALL PMID를 기본 키로 사용하여 동일한 PMID를 가진 Article 중 입력 목록에서 첫 번째로 등장한 Article만 유지하고 나머지를 제거한다.
2. WHEN 두 Article이 서로 다른 PMID를 가지지만 동일한 non-null DOI를 가지면, THE Deduplicator SHALL 두 Article을 모두 결과에 포함하고 경고 로그를 기록하며, 두 Article 중 어느 것도 제거하지 않는다.
3. WHEN PMID가 null인 Article이 존재하면, THE Deduplicator SHALL 해당 Article을 결과에 포함하지 않고 검증 경고 로그를 기록한다.
4. WHEN Article 목록이 중복 제거 처리를 완료하면, THE Deduplicator SHALL 결과 목록 내 모든 PMID 값이 null이 아니고 고유한지 보장한다.
5. WHEN 중복이 포함된 Article 목록에 대해 중복 제거를 두 번 연속 적용하면, THE Deduplicator SHALL 두 번째 적용 결과가 첫 번째 적용 결과와 동일한 Article 목록을 반환한다.

---

### Requirement 4: 연구 대상 종 분류 및 불확실성 표시

**User Story:** As a 연구 담당자, I want 각 논문의 연구 대상 종이 명확히 표시되기를 원한다, so that 개 대상 연구와 사람 대상 연구를 혼동하지 않고 근거를 적절히 평가할 수 있다.

#### Acceptance Criteria

1. WHEN Article의 종 분류가 요청되면, THE Species_Classifier SHALL NCBI가 제공하는 구조화된 메타데이터(MeSH 용어, Article type 등)를 1차 근거로 사용하고, 제목과 초록 키워드를 2차 보조 근거로 사용하여 Species_Status(`dog_confirmed`, `cat_confirmed`, `human_confirmed`, `multi_species`, `unverified`) 중 하나를 부여한다.
2. THE Species_Classifier SHALL `confirmed` 상태를 부여하기 위해 다음 조건을 모두 충족해야 한다: (a) 해당 종이 단순 언급이나 비교 대상이 아닌 실제 실험 대상임을 나타내는 근거가 1차 또는 2차 출처에 존재하고, (b) 다른 종이 실험 대상임을 나타내는 상충 근거가 없어야 한다. 두 조건 중 하나라도 충족하지 못하면 `unverified`를 부여한다.
3. THE Species_Classifier SHALL 다음 우선순위 규칙에 따라 Species_Evidence_Strength를 결정한다: (a) 구조화된 메타데이터(MeSH 용어, Article type 등)에서 해당 종이 실험 대상임을 명시한 경우 `high`, (b) 구조화된 메타데이터에 근거가 없고 제목에서 해당 종이 실험 대상임을 명시한 경우 `medium`, (c) 구조화된 메타데이터와 제목 모두에 근거가 없고 초록에만 관련 키워드가 포함된 경우 `low`.
4. THE Species_Classifier SHALL 논문에서 특정 종을 단순 언급하거나 비교 대상으로만 사용한 경우를 실제 실험 대상 종과 구분하며, 실험 대상 종을 확정할 근거가 없으면 `unverified`를 부여한다.
5. IF 1차 및 2차 근거가 상충하면(예: 구조화된 메타데이터는 human을 가리키는데 제목은 canine을 실험 대상으로 명시), THEN THE Species_Classifier SHALL Species_Status를 `unverified`로 설정하고 상충 사실을 분류 근거에 기록한다.
6. IF 1차 및 2차 근거에서 두 종 이상이 실험 대상으로 확인되면, THEN THE Species_Classifier SHALL Species_Status를 `multi_species`로 설정한다.
7. WHEN 종 분류가 완료되면, THE Species_Classifier SHALL 분류 결과(Species_Status), 증거 강도(Species_Evidence_Strength), 분류에 사용된 근거(사용된 MeSH 용어 또는 키워드 목록)를 Article에 기록한다.
8. IF 제목과 초록이 모두 null이고 구조화된 메타데이터에도 종 정보가 없으면, THEN THE Species_Classifier SHALL Species_Status를 `unverified`, Species_Evidence_Strength를 `low`로 설정한다.
9. IF Species_Status가 `unverified`이면, THEN THE Streamlit_UI SHALL 해당 논문 카드에 "종 미확인" 레이블을 표시한다.

---

### Requirement 5: 논문 검색 결과 조회 화면

**User Story:** As a 연구 담당자, I want Streamlit 화면에서 검색 조건을 입력하고 결과를 탐색할 수 있기를 원한다, so that 별도의 개발 환경 없이 논문 근거를 빠르게 확인할 수 있다.

#### Acceptance Criteria

1. THE Streamlit_UI SHALL 유전자명(필수), 종(dog/cat/human/all, 필수), 연도 범위(필수), 암종 키워드(선택) 입력 필드와 검색 버튼을 제공한다.
2. WHEN 검색이 완료되면, THE Streamlit_UI SHALL 각 Article에 대해 제목, 출판연도, 저널, PMID, Species_Status, 초록 유무, PubMed 원문 링크를 논문 카드 형태로 표시하며, 결과는 최대 200건을 출판연도 내림차순으로 표시한다.
3. WHEN 검색 결과 화면이 표시되면, THE Streamlit_UI SHALL ESearch 전체 검색 건수(total_count)와 실제 표시된 논문 건수(returned_count), 사용자 검색 시각(searched_at, UTC ISO 8601)을 함께 표시한다.
4. IF abstract_available이 false이면, THEN THE Streamlit_UI SHALL 해당 카드에 "초록 없음" 문구를 표시한다.
5. WHEN 검색이 완료되면, THE Streamlit_UI SHALL 검색 결과를 `dog_confirmed` / `cat_confirmed` / `human_confirmed` / `multi_species` / `unverified` 그룹으로 구분된 섹션 헤더와 함께 표시한다.
6. THE Streamlit_UI SHALL 논문 카드의 PubMed 원문 링크를 새 탭에서 열 수 있는 방식으로 제공한다.
7. IF 검색 결과가 0건이면, THEN THE Streamlit_UI SHALL "설정한 조건에서 검색된 연구 없음" 메시지를 표시한다.
8. IF 검색 중 오류가 발생하면, THEN THE Streamlit_UI SHALL 오류 메시지를 표시하고 이전에 입력한 검색 조건 값을 유지한다.

---

### Requirement 6: NCBI API 호출 안정성 및 속도 제한 준수

**User Story:** As a 개발자, I want 외부 API 오류나 네트워크 문제가 발생해도 명확한 오류 메시지를 받고 싶다, so that 오류 상황과 검색 결과 없음을 혼동하지 않고 적절히 대응할 수 있다.

#### Acceptance Criteria

1. THE NCBI_Client SHALL API 키가 설정되지 않은 경우 초당 최대 3회, API 키가 설정된 경우 초당 최대 10회를 초과하지 않도록 요청 속도를 제한한다.
2. THE NCBI_Client SHALL 모든 외부 API 호출에 타임아웃(기본값: 30초)을 설정하며, 타임아웃 초과 시 연결을 즉시 종료하고 타임아웃 오류를 호출자에게 전달한다.
3. WHEN NCBI API가 HTTP 429(Too Many Requests)를 반환하면, THE NCBI_Client SHALL 요청 속도 제한을 유지하면서 1초, 2초, 4초 간격의 지수 백오프를 적용하여 최대 3회 재시도하며, 3회 소진 후에도 429가 반환되면 오류를 호출자에게 전달한다.
4. WHEN NCBI API가 HTTP 5xx 오류를 반환하면, THE NCBI_Client SHALL 최대 2회 재시도 후 오류를 호출자에게 전달한다.
5. WHEN ESearch는 성공했지만 EFetch 배치 호출 중 일부가 실패하면, THE Search_Service SHALL 성공한 배치의 Article만 결과에 포함하고 실패한 PMID 목록과 사유를 로그에 기록하며, 응답에 `is_partial: true`와 실패한 PMID 수를 포함하는 부분 성공 응답을 반환한다.
6. IF NCBI API 응답에 PMID가 없으면, THEN THE PubMed_Parser SHALL 해당 항목을 결과에서 제외하고 제외된 항목 수와 사유를 포함하는 경고 로그를 기록한다.
7. IF 타임아웃, 네트워크 오류, 또는 HTTP 429 재시도 3회 소진이 발생하면, THEN THE FastAPI_Server SHALL HTTP 503을 반환한다.
8. IF HTTP 5xx 재시도가 2회 소진되면, THEN THE FastAPI_Server SHALL HTTP 502를 반환한다.
9. THE Streamlit_UI SHALL API 오류 발생 시 오류 유형(네트워크 오류, 부분 성공, 파싱 오류)을 구분하여 표시하며, 정상 처리 후 0건인 경우와 오류로 인한 0건을 다른 메시지로 구분한다.

---

### Requirement 7: 검색 결과 캐시 및 저장

**User Story:** As a 개발자, I want 검색 결과가 로컬에 저장되기를 원한다, so that 동일한 검색을 반복하더라도 불필요한 외부 API 호출을 줄일 수 있다.

#### Acceptance Criteria

1. THE SQLite_Cache SHALL gene, species, year_from, year_to, cancer_keyword, limit 전체를 정규화하여 Cache_Key를 생성하고, 이를 기준으로 검색 결과를 저장 및 조회한다.
2. WHEN 동일한 Cache_Key로 재검색하고 해당 캐시의 cached_at이 현재 시각 기준 24시간 이내이면, THE Search_Service SHALL SQLite_Cache에서 기존 결과를 반환하며 외부 API를 재호출하지 않는다.
3. WHEN 캐시에서 결과를 반환할 때, THE Search_Service SHALL searched_at을 캐시 저장 시각(cached_at)이 아닌 현재 요청 시각으로 설정하며, THE Streamlit_UI SHALL 논문 카드에 ncbi_retrieved_at(NCBI 데이터 수집 시각)을 표시하고 searched_at(현재 조회 시각)과 구분하여 표시한다.
4. THE SQLite_Cache SHALL 각 저장된 Article에 PMID, DOI(없으면 NULL 허용), ncbi_retrieved_at, Cache_Key를 함께 기록하며, 캐시 항목에는 cached_at을 별도로 기록한다.
5. THE SQLite_Cache SHALL PMID를 기본 키로 사용하여 동일한 PMID의 Article이 중복 저장되지 않도록 보장하며, PMID가 null인 Article은 저장 대상에서 제외한다.
6. IF SQLite_Cache 저장 중 오류가 발생하면, THEN THE Search_Service SHALL 캐시 오류를 로그에 기록하고 해당 오류가 검색 결과 반환에 영향을 주지 않도록 보장한다.
7. WHEN 외부 API로부터 Article 데이터를 수신하고 중복 제거가 완료된 직후, IF 응답의 `is_partial`이 false인 경우에만, THEN THE Search_Service SHALL 결과 Article 목록을 SQLite_Cache에 저장한다.

---

### Requirement 8: 검색 데이터 신뢰성 보장

**User Story:** As a 연구 담당자, I want 모든 검색 결과가 실제 API에서 수집된 자료임을 신뢰할 수 있기를 원한다, so that 논문 정보를 의사결정의 참고 자료로 활용할 때 출처를 검증할 수 있다.

#### Acceptance Criteria

1. THE Search_Service SHALL Article의 PMID, DOI, 제목, 출판연도, 저자 정보를 NCBI API 응답의 해당 필드에서 직접 매핑하여 저장하며, 해당 필드들의 값은 NCBI API 응답에 존재하지 않는 경우 null로 저장하고 임의로 생성하거나 다른 필드에서 추론하지 않는다.
2. WHEN 검색 결과 화면이 표시될 때, THE Streamlit_UI SHALL "검색 기준: NCBI PubMed, 검색 시각: {searched_at}" 문구를 표시하며, searched_at은 UTC 기준 ISO 8601 형식으로 표시한다.
3. THE Search_Service SHALL MVP 범위에서 수집되는 모든 Article 필드(PMID, DOI, 제목, 초록, 저자, 출판연도, 저널명)를 NCBI API에서 직접 수집한 데이터로만 채우며, 향후 AI 요약 기능 추가 시 원본 Article 모델을 수정하지 않고 별도 모델로 관리할 수 있도록 설계한다.
4. WHEN Article이 저장될 때, IF source_url이 `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` 형식을 따르지 않으면, THEN THE Search_Service SHALL 해당 Article의 source_url을 null로 저장하고 검증 실패를 로그에 기록한다.
5. THE Search_Service SHALL NCBI API 응답에서 수집한 PMID, DOI, 제목, 저자 등 원본 식별자 및 서지 정보를 수정하거나 재생성하지 않는다.

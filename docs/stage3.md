# 3단계: 최소 Streamlit UI

검증일: 2026-10-27. Python 3.12.15 Conda 환경, Streamlit 1.66.1.

`frontend/app.py`는 기존 Pydantic API 계약을 재사용하고 FastAPI `POST /search`만
HTTP로 호출한다. NCBI 클라이언트나 검색 서비스는 프론트엔드에서 호출하지 않는다.
인증 설정은 백엔드에서만 읽는다.

## 검증 결과

- 전체 pytest: 118 passed, 4 skipped (기본 실행에서 live 테스트 제외).
- 별도 live API 테스트: 4 passed, 118 deselected.
- 신규 UI 테스트 13개: 실제 응답 기반 데이터, 누락값, 입력 검증, 빈 결과,
  부분 성공, 전체 수집 실패, 서버 오류, 연결 실패, 시간 초과, 잘못된 응답 검증.
- `pip check`: 의존성 충돌 없음.
- Chrome에서 Streamlit → FastAPI → 실제 NCBI 검색을 확인했다.

| 조건 | total_count | returned_count | 반환 PMID |
| --- | ---: | ---: | --- |
| BRAF, dog, limit=3 | 93 | 3 | 42775191, 42847792, 42680778 |
| TP53, dog, limit=3 | 84 | 3 | 42580051, 42930160, 42018306 |

두 검색 모두 부분 성공이 아닌 정상 완료였다. BRAF 초록 펼치기와 PubMed 원본
버튼을 확인했으며, 원본 페이지의 제목과 PMID 42775191이 일치했다.
검색 결과 건수는 NCBI 갱신에 따라 바뀔 수 있다.

화면 기록: [BRAF 초록](streamlit-braf-browser.jpg),
[TP53 결과](streamlit-tp53-browser.jpg).

## 설계와 현재 범위

- 기존 설계의 UI 구조 대신 합의된 `frontend/app.py` 단일 파일을 사용한다.
- 연도는 현재 API 계약대로 선택 입력이며, 종별 확정 그룹은 만들지 않는다.
  모든 논문은 `unverified`이며 MeSH 필터가 실제 연구 대상 종의 확정이 아님을 표시한다.
- SQLite, AI 요약, 종 확정 분류, 로그인, 배포는 구현하지 않았다.
- 현재 결과만 Streamlit 세션 메모리에 보관한다. 검색 캐시는 없다.
- UI 응답 대기는 180초이며, 초과 후에도 백엔드 검색이 진행 중일 수 있다.
- 요구사항·설계 원문과 기존 백엔드는 변경하지 않았다.

실행 명령은 루트 README의 11절을 참고한다. 검증용 임시 서버는 종료했다.
기존 README 삭제 상태와 미추적 파일은 그대로 두었으며 커밋하지 않았다.

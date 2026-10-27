# React 프론트엔드 교체 검증

검증일: 2026-10-27. Python 3.12.15 Conda, Node.js 24.20.0.

## 구현

- frontend/ 안에 React + TypeScript + Tailwind CSS + Vite를 구성했다.
- 기존 frontend/app.py, Streamlit 의존성과 테스트, Python 백엔드 및 API 계약은 보존했다.
- 브라우저의 POST /api/search를 Vite 프록시가 FastAPI POST /search로 전달한다.
- 시스템 폰트, 밝은 배경, 네이비·청록 색상, 결과 중심 두 열 레이아웃을 사용한다.
- 모바일에서는 한 열로 전환한다. 논문 제목·저자·초록·PMID·DOI·원본 링크와
  누락값, 종 미확인, 부분 성공, 정상 0건, 입력 및 서버 오류를 구분한다.
- 검색 상세에서 UTC 검색 시각·검색식·NCBI 경고를 확인할 수 있다.
- API 응답 구조와 건수 정합성을 런타임에 검사한다. 실제 응답 fixture는 테스트에서만
  사용하며 서비스 화면에 논문 데이터를 하드코딩하지 않는다.
- HTTP 요청에는 180초 제한을 두고 중복 제출과 이전 응답의 덮어쓰기를 방지한다.

## 실행

루트에서 Conda 환경을 활성화하고 FastAPI를 실행한다.

```bash
conda activate canine-evidence
uvicorn canine_evidence.api:app --host 127.0.0.1 --port 8000
```

다른 터미널에서:

```bash
cd frontend
npm ci
npm run dev
```

기본 화면: http://127.0.0.1:5173 . 다른 백엔드는 Vite 실행 환경변수
CANINE_API_URL로 지정한다. 백엔드 .env와 NCBI 인증 정보는 프론트엔드로 복사하지 않는다.

## 검증 결과

- npm test: 19 통과, 0 실패.
- npm run typecheck: 통과.
- npm run build: 통과. frontend/dist/ 생성.
- 전체 pytest: 118 통과, 0 실패, 4 건너뜀 (기본 제외되는 live 테스트).
- 이번 작업의 실시간 연동 검증은 실제 Chrome → React → Vite → FastAPI → NCBI로 수행했다.
- BRAF / dog / limit=3: 전체 93건, 반환 3건, 정상 완료.
  PMID: 42775191, 42847792, 42680778.
- TP53 / dog / limit=3: 전체 84건, 반환 3건, 정상 완료.
  PMID: 42580051, 42930160, 42018306.
- 모바일 viewport 390 × 844에서 한 열 배치와 가로 넘침 없음을 확인했다.
- 초록 펼치기/접기와 새 탭 PubMed 이동을 확인했다. PMID 42580051의 원본 제목이
  화면의 논문 제목과 일치했다.
- 실제 NCBI 장애를 유발하지 않았다. 오류·부분 성공·누락값은 fixture 기반 Mock 테스트다.

화면 기록:

- [BRAF 데스크톱](react-braf-desktop.jpg)
- [TP53 모바일](react-tp53-mobile.jpg)

## 범위와 남은 제한

React를 기본 UI로 안내한다. 기존 설계 문서의 Streamlit 선택과는 다르며,
사용자가 승인한 프론트엔드 교체에 한정한 변경이다. 요구사항·설계 원문은 변경하지 않았다.
SQLite, AI 요약, 종 확정 분류, 로그인, 배포는 이번 범위에 포함하지 않았다.

Vite 프록시는 개발용이다. 정적 프로덕션 빌드에는 API 프록시가 포함되지 않으므로
실제 배포 시 동일 출처 프록시가 필요하다. UI 타임아웃은 서버의 NCBI 작업을 취소하지 않는다.
실제 검색 건수는 PubMed 갱신에 따라 달라질 수 있다.

검증용 서버는 종료했다. 기존 Git 삭제 상태와 미추적 파일을 임의로 정리하거나
커밋하지 않았다.

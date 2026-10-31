# AI-CRAWLER

기존 쇼핑 플랫폼 크롤러의 한계를 개선하기 위해, 다양한 소스의 데이터를 일관되게 수집·정제·검증하는 **AI 기반 통합 콘텐츠 수집 시스템**을 목표로 합니다.

## 해결하려는 문제
- 플랫폼별 크롤러 구현 방식이 달라 유지보수가 어렵다.
- 수집 데이터 포맷이 제각각이라 후처리 비용이 크다.
- 중복/저품질/오류 콘텐츠에 대한 검증이 수동에 가깝다.

## AI 기반 통합 수집 아키텍처
1. **수집 계층(Ingestion)**  
   쇼핑 플랫폼별 커넥터가 원본 데이터를 수집합니다.
2. **정규화 계층(Normalization)**  
   상품명, 가격, 카테고리, 옵션, 이미지 등 공통 스키마로 변환합니다.
3. **AI 검증 계층(Validation)**  
   중복 탐지, 이상치 탐지, 품질 점수화를 통해 데이터 신뢰도를 높입니다.
4. **저장/배포 계층(Storage & Delivery)**  
   정제된 데이터를 저장하고, 검색/추천/분석 시스템으로 전달합니다.

## 여러 개발자에게 검증된 프로세스
아래 프로세스는 팀 단위 협업에서 반복적으로 사용되는 검증 흐름을 기준으로 합니다.

1. **이슈 기반 작업 시작**
   - 문제 정의(현상/원인/기대결과)를 이슈에 명확히 기록
   - 영향 범위를 수집/정규화/AI 검증/저장 계층으로 분리
2. **작은 단위 변경**
   - 하나의 PR은 하나의 목적(커넥터 추가, 스키마 변경, 검증 룰 개선 등)만 포함
   - 리뷰 가능성을 높이기 위해 작은 커밋으로 분리
3. **검증 우선 개발**
   - 변경 대상에 대한 최소 재현 시나리오 작성
   - 데이터 정합성(필수 필드, 타입, 중복률) 확인
4. **리뷰 체크리스트 고정**
   - 수집 안정성(재시도/타임아웃/차단 대응)
   - 정규화 호환성(기존 스키마와의 하위 호환)
   - AI 검증 정확성(오탐/미탐 기준)
   - 보안/개인정보/비밀정보 노출 여부
5. **배포 후 관측**
   - 수집 성공률, 중복률, 오류율, 처리 지연 지표 모니터링
   - 임계치 초과 시 롤백 또는 룰 재학습

## 품질 기준(Definition of Done)
- 신규/변경 수집 로직이 공통 스키마를 통과한다.
- AI 검증 결과(중복·이상치·품질 점수)가 기록 가능하다.
- 리뷰 체크리스트 항목을 모두 충족한다.
- 운영 지표(성공률/오류율/지연시간)를 확인할 수 있다.

AI 기반 대규모 멀티 플랫폼 콘텐츠 수집 시스템의 YouTube POC입니다.

## 현재 진행 단계

현재 저장소는 **2단계: 실행 기반과 데이터 모델 구현 중**입니다. 이 단계에서는 구현되지 않은 기능을 완료로 표시하지 않으며, 각 후속 단계는 테스트를 통과한 뒤 진행합니다.

## 목표와 범위

- 자연어 요청을 검색 계획으로 변환하고 등록된 Tool만 호출합니다.
- YouTube Data API v3로 공개 영상의 발견 및 메타데이터를 수집합니다.
- 검색/메타데이터 수집과 권한이 확인된 미디어 파일 수신·저장을 분리합니다.
- 일반 공개 YouTube 영상은 공식 임베드 플레이어로만 제공합니다.
- YouTube의 사전 서면 승인이나 적절한 권리·접근 권한 없는 원본 다운로드 기능은 제공하지 않습니다.
- 플랫폼별 Collector와 권한 있는 Media Provider를 공통 인터페이스 뒤에 배치해 확장합니다.

## 논리 아키텍처

```text
React Dashboard
        |
     FastAPI
        |
   AI Agent (Tool Calling)
        |
 Collection Manager
        |
 Redis / Celery
        |
 +------+------+------+------+------+
 |      |      |      |      |      |
Discovery Metadata Comment Media Validation
 Worker   Worker   Worker  Ingestion Worker
        |       |       |       |
        +-------+-------+-------+
                |
       PostgreSQL / MinIO
```

### 책임 경계

| 영역 | 책임 | 금지 사항 |
|---|---|---|
| Agent | 요청 분석, 키워드·조건 생성, Collector Tool 선택, 작업 계획 | 영상 한 건마다 LLM 호출, 브라우저 무제한 조작 |
| Collector | 공식 API를 이용한 발견, 메타데이터, 댓글, 자막 접근 | 권한 없는 원본 미디어 다운로드 |
| Collection Manager | 작업 생성, 상태 전이, 재시도·중단·재개 조정 | 플랫폼별 API 로직 중복 구현 |
| Worker | 반복적인 비동기 수집 및 검증 | 작업 계획을 임의로 변경 |
| Media Provider | 권한 검증 후 파일 수신, 검증, MinIO 저장 | 권한 증빙 없는 파일 저장 |
| PostgreSQL | 상태·메타데이터·출처·권한 증빙·감사 로그 | 미디어 바이너리 저장 |
| MinIO | 권한 확인된 미디어 객체 저장 | DB 상태를 대체하는 업무 로직 저장 |

## 프로젝트 디렉터리 구조

구조는 기능별 모듈과 배포 경계를 분리합니다. 실제 디렉터리와 파일은 해당 단계에서 구현될 때 추가됩니다.

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 # HTTP 라우터와 요청/응답 모델
│   │   ├── agent/               # Agent 계획, Tool registry, 실행 이력
│   │   ├── collectors/          # BaseCollector 및 YouTube 구현
│   │   ├── core/                # 설정, 로깅, 보안, 오류
│   │   ├── db/                  # SQLAlchemy 모델, 세션, 마이그레이션
│   │   ├── media/               # BaseMediaProvider 및 권한 있는 공급자
│   │   ├── services/            # 작업 조정, 할당량, 중복 제거
│   │   ├── workers/             # Celery task와 재시도 정책
│   │   └── main.py              # FastAPI 진입점
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── load/
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/            # Dashboard, Collection, Monitor, Library, Agent
│   │   ├── lib/                 # API client와 공통 유틸리티
│   │   ├── types/
│   │   └── main.tsx
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   ├── docker/
│   ├── prometheus/
│   └── grafana/
├── db/
│   └── migrations/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── erd.md
│   └── performance.md
├── docker-compose.yml
└── .env.example
```

## 핵심 데이터 모델

최소 테이블은 다음 관계를 갖습니다.

```text
collection_jobs
  └── collection_tasks ── collection_keywords
          └── platform_sources
          └── videos ── video_comments
                    ├── video_captions
                    └── media_assets ── media_rights

collection_jobs ── collection_logs
                 └── api_usage_logs
agent_executions ── collection_jobs
```

- `videos`의 메타데이터 상태와 `media_assets`의 미디어 상태는 독립적으로 관리합니다.
- `videos.platform_video_id`와 `platform_sources` 조합을 중복 방지 키로 사용합니다.
- `media_rights`는 권한 주체, 허용 범위, 증빙 위치, 검증 시각을 기록합니다.
- `api_usage_logs`는 API 종류·비용·쿼터·응답 결과를 기록해 부족 시 작업을 대기 상태로 전환할 수 있게 합니다.
- 상태 변경과 외부 API 결과는 `collection_logs`에 남겨 재처리와 감사가 가능해야 합니다.

## 단계별 구현 계획과 완료 조건

### 1단계 — 아키텍처 및 구조 설계

- [x] 책임 경계와 권한 제한 정의
- [x] 프로젝트 디렉터리 계약 정의
- [x] 최소 데이터 모델 관계와 상태 분리 정의
- [x] 단계별 검증 기준 정의

### 2단계 — 실행 기반과 데이터 모델 (진행 중)

- [x] FastAPI health endpoint, 설정 검증, 구조화 로그
- [x] SQLAlchemy 모델과 Alembic 초기 마이그레이션
- [x] PostgreSQL/Redis/MinIO 로컬 Compose 구성
- [ ] 완료 조건: 마이그레이션 적용, health check, DB 연결 테스트 통과

현재 환경에서는 Docker Desktop Linux Engine이 실행되지 않아 PostgreSQL 컨테이너와 마이그레이션 적용을 아직 검증하지 못했습니다.

### 3단계 — YouTube 발견·메타데이터 수집

- 검색 페이지네이션, 기간·정렬 조건, 상세·채널·댓글·자막 접근
- API 할당량 원장과 대기 상태 전환
- 중복 제거 및 재시도 정책
- 완료 조건: API mock 기반 검색·페이지네이션·중복·쿼터·실패 테스트 통과

### 4단계 — Agent와 비동기 작업

- Tool registry, 검색 계획 검증, Celery worker 분리
- 작업 중단·재개·우선순위·실패 재처리
- 완료 조건: Agent 실행 이력과 worker 상태가 API에서 추적되고 통합 테스트 통과

### 5단계 — 권한 있는 미디어 수신 및 저장

- `BaseMediaProvider`와 권한 증빙 검증
- MP4/스트림/크기/길이/ SHA-256 검증, MinIO 저장
- 완료 조건: 권한 없는 입력 거부, 권한 있는 테스트 파일 저장·무결성 테스트 통과

### 6단계 — React 대시보드

- Dashboard, AI Collection, Monitor, Library, Detail, Agent History
- 공식 YouTube 임베드와 미디어 상태 분리 표시
- 완료 조건: API mock 기반 주요 화면·상태·오류 표시 테스트 통과

### 7단계 — 부하·운영 검증

- 합성 데이터 부하 테스트와 실제 API 성능을 별도 기록
- Prometheus/Grafana 지표, Docker 배포 문서, API/ERD 문서
- 완료 조건: 처리량·할당량·실패율·저장 성능 결과를 재현 가능한 방식으로 기록

## 개발 원칙

1. 공식 API와 적법한 접근 경로를 우선하며, 권한이 불명확한 콘텐츠는 저장하지 않습니다.
2. Agent는 계획과 Tool 선택만 담당하고, 반복 수집은 Worker가 담당합니다.
3. API 할당량 부족은 무한 재시도가 아니라 명시적인 대기 상태로 처리합니다.
4. 실제 수집 데이터와 샘플·합성 데이터를 구분합니다.
5. 각 단계의 완료 조건과 테스트를 통과하기 전 다음 단계로 진행하지 않습니다.

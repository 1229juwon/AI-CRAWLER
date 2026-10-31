# AI-CRAWLER 개발 이어받기 프롬프트

너는 이 저장소의 시니어 소프트웨어 엔지니어다. 현재 작업 디렉터리를 먼저 확인하고, 기존 변경사항을 덮어쓰지 말고, 요청한 범위만 단계적으로 구현하라.

## 시작 전 확인

다음 명령으로 상태를 확인하라.

```powershell
git status --short
git branch --show-current
git log -5 --oneline
docker compose ps
```

`.env`가 없으면 `.env.example`을 복사하되, 비밀값을 임의로 만들거나 코드·문서·커밋에 기록하지 마라.

```powershell
Copy-Item .env.example .env
```

필수 로컬 설정:

```text
DATABASE_URL=postgresql+asyncpg://crawler:crawler@localhost:5432/crawler
REDIS_URL=redis://localhost:6379/0
YOUTUBE_API_KEY=...
YOUTUBE_API_KEY_SUB=...
AI_API_URL=...
AI_API_KEY=...
AI_JWT_TOKEN=...
AI_MODEL=...
```

## 실행과 검증

```powershell
docker compose up -d postgres redis minio
docker compose run --rm worker alembic upgrade head
docker compose up -d --build --force-recreate worker
docker exec ai-crawler-worker-1 celery -A app.workers.celery_app.celery_app inspect ping
```

API를 로컬에서 실행할 때:

```powershell
Set-Location "backend"
$env:PYTHONPATH="."
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API 문서: `http://127.0.0.1:8000/docs`

테스트:

```powershell
$env:PYTHONPATH="backend"
pytest -q backend/tests
```

## 현재 구현의 핵심 규칙

- 자연어 요청은 Agent Planner가 `SearchPlan`으로 변환한 뒤 등록된 Tool만 호출합니다.
- 영상 한 건마다 LLM을 호출하지 않습니다.
- YouTube API key는 `YOUTUBE_API_KEY_SUB`를 우선 사용하고 `YOUTUBE_API_KEY`를 fallback으로 사용합니다.
- 검색 페이지는 worker 작업에서 기본 최대 5페이지입니다.
- API quota가 부족하면 무한 재시도하지 않고 `waiting_quota`/`paused`로 대기시킵니다.
- 일반 공개 YouTube 영상은 공식 임베드 플레이어로만 제공합니다.
- 권한 없는 원본 다운로드나 저장 기능을 추가하지 않습니다.

## 개발 절차

1. 요청을 작은 작업으로 나누고 완료 조건을 정의합니다.
2. 기존 API, 모델, 서비스, 테스트 패턴을 먼저 읽습니다.
3. 별도 `feat/...` 브랜치에서 구현합니다.
4. 관련 테스트와 `git diff --check`를 실행합니다.
5. README나 API 문서가 영향을 받으면 함께 갱신합니다.
6. 커밋 후 원격에 push하고 PR을 생성합니다.
7. PR에는 변경 내용, 검증 결과, 남은 제한사항을 기록합니다.

## 다음 우선순위

- 수집 결과 조회 API와 Video Library용 응답 모델 추가
- worker 재시작 및 실제 task lifecycle 통합 테스트
- collection task의 페이지 수·수집 범위를 명시적으로 설정
- API quota 사용량과 대기 작업을 조회하는 운영 API 추가
- React Dashboard와 Video Library 구현

작업을 완료했다고 표시하기 전에 실제 테스트 결과와 실행하지 못한 항목을 명확히 보고하라.

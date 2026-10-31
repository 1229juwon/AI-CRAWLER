# 개발 이어받기 프롬프트

이 폴더의 프롬프트는 다른 PC에서 AI-CRAWLER 개발을 이어갈 때 사용합니다.

## 사용 순서

1. 새 PC에 저장소를 clone합니다.
2. [`continue-development.md`](./continue-development.md)를 새 대화에 붙여 넣습니다.
3. AI에게 먼저 저장소 상태, 브랜치, 테스트, Docker 상태를 점검하게 합니다.
4. `.env.example`을 복사해 `.env`를 만들고 실제 비밀값은 로컬에서만 입력합니다.
5. 수집 결과를 확인하려면 [`verify-collection.md`](./verify-collection.md)를 사용합니다.

## 보안

- API key, JWT, 비밀번호, 내부 URL은 이 폴더나 Git에 기록하지 않습니다.
- 비밀값은 새 PC의 `.env`에 직접 입력합니다.
- 이미 노출된 자격 증명은 폐기하고 재발급해야 합니다.
- YouTube 공개 영상 원본 다운로드 기능은 구현하지 않습니다. 권한이 확인된 미디어만 별도 Media Provider에서 처리합니다.

## 현재 기준점

- 기본 브랜치에 병합된 이전 구현을 기준으로 작업합니다.
- YouTube Data API v3 검색·메타데이터·댓글·자막 수집 골격이 있습니다.
- FastAPI, PostgreSQL, Redis, Celery, MinIO Docker 구성이 있습니다.
- quota가 부족하면 작업은 `waiting_quota`와 `paused` 상태로 전환됩니다.
- 현재 프론트엔드는 아직 구현 대상이며 API와 worker 검증이 우선입니다.

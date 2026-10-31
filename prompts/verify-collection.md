# 수집 결과 확인 프롬프트

AI-CRAWLER의 실제 YouTube 수집 결과를 확인하라. 비밀값은 출력하지 말고, 작업 상태와 저장 건수만 보고하라.

## API 작업 상태

API를 실행한 뒤 다음 endpoint를 조회합니다.

```text
GET http://127.0.0.1:8000/collection-jobs/{job_id}
```

`job_id`는 하드코딩하지 말고 최근 작업 생성 응답이나 PostgreSQL에서 확인합니다.

상태 의미:

- `pending`: 대기 중
- `running`: 수집 중
- `completed`: 완료
- `waiting_quota`: YouTube quota 부족으로 대기
- `paused`: job 일시정지
- `failed`: 오류 종료

## PostgreSQL 조회

```powershell
docker exec -it ai-crawler-postgres-1 psql -U crawler -d crawler
```

```sql
SELECT
  platform_video_id,
  title,
  channel_name,
  published_at,
  view_count,
  metadata_status,
  media_status
FROM videos
ORDER BY created_at DESC
LIMIT 50;

SELECT count(*) AS videos FROM videos;
SELECT count(*) AS comments FROM video_comments;
SELECT count(*) AS captions FROM video_captions;
SELECT status, count(*) FROM collection_tasks GROUP BY status;
```

## 결과 보고 형식

다음 항목을 포함해 보고합니다.

1. job/task ID
2. job status와 task status
3. discovered/metadata/comments/captions 건수
4. PostgreSQL 실제 저장 건수
5. quota 오류 또는 API 오류
6. 다시 실행할 수 있는지 여부

`waiting_quota`인 경우 무작정 재시도하지 말고 quota 회복 또는 유효한 키 교체 후 resume합니다.

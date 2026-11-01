#!/bin/bash
set -e

until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"; do
  echo "Waiting for MinIO..."
  sleep 2
done

mc mb local/"$MINIO_BUCKET" --ignore-existing 2>/dev/null || true
echo "MinIO bucket '$MINIO_BUCKET' ready."
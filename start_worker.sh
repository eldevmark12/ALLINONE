#!/bin/bash
set -e
cd "$(dirname "$0")/backend"
exec celery -A tasks.celery_app worker --loglevel=info --concurrency=4

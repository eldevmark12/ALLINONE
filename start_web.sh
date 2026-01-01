#!/bin/bash
set -e
cd "$(dirname "$0")/backend"
exec gunicorn -w 4 --bind 0.0.0.0:$PORT --timeout 120 app:app

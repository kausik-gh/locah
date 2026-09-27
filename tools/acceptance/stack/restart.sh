#!/usr/bin/env bash
# Restart one local acceptance service by name: api | workspace | web | auth.
# Kills whatever listens on its port, then starts it detached, logging to
# acceptance-out/<name>.log.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
mkdir -p acceptance-out
case "$1" in
  api) port=${API_PORT:-8010}; cmd="bash tools/acceptance/stack/api.sh" ;;
  workspace) port=${WORKSPACE_PORT:-3101}; cmd="bash tools/acceptance/stack/workspace.sh" ;;
  web) port=${WEB_PORT:-3100}; cmd="bash tools/acceptance/stack/web.sh" ;;
  auth) port=54321; cmd="node tools/acceptance/stack/mock-auth.mjs" ;;
  *) echo "usage: $0 api|workspace|web|auth" >&2; exit 2 ;;
esac
listeners() {
  if command -v ss >/dev/null; then ss -ltnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2
  elif command -v lsof >/dev/null; then lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null
  fi
}
for pid in $(listeners || true); do kill "$pid" 2>/dev/null || true; done
for i in $(seq 1 20); do [ -z "$(listeners || true)" ] && break; sleep 0.5; done
if [ -n "$(listeners || true)" ]; then echo "port $port is still held; not starting a second $1" >&2; exit 1; fi
setsid nohup $cmd > "acceptance-out/$1.log" 2>&1 < /dev/null &
for i in $(seq 1 90); do
  if curl -s -o /dev/null "http://localhost:$port/" 2>/dev/null; then echo "$1 up on :$port"; exit 0; fi
  sleep 1
done
echo "$1 did not come up; see acceptance-out/$1.log" >&2; exit 1

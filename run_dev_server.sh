#!/usr/bin/env bash
# Start the provenance explorers dev server from the repo root.
#
# Usage:
#   ./run_dev_server.sh              # install deps if needed, then run on :5180
#   ./run_dev_server.sh --build      # production build + preview server instead
#   ./run_dev_server.sh --fresh      # wipe node_modules and reinstall
#
# Pages: / (FMR), /nia.html, /nia-titles.html, /dpwh.html, /about.html
set -euo pipefail
cd "$(dirname "$0")"

MODE="dev"
FRESH=0
for arg in "$@"; do
  case "$arg" in
    --build) MODE="preview" ;;
    --fresh) FRESH=1 ;;
    *) echo "Unknown option: $arg (use --build or --fresh)" >&2; exit 2 ;;
  esac
done

if [ ! -x "$(command -v node)" ]; then
  echo "Node.js not found — install Node 22+ first: https://nodejs.org" >&2
  exit 1
fi
MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$MAJOR" -lt 22 ]; then
  echo "Node 22+ required (found $(node --version))" >&2
  exit 1
fi

if [ "$FRESH" -eq 1 ]; then
  echo "» Removing web/node_modules for a clean install…"
  rm -rf web/node_modules
fi

# Install dependencies when missing or when the lockfile is newer.
if [ ! -d web/node_modules ] || [ web/package-lock.json -nt web/node_modules/.package-lock.json ]; then
  echo "» Installing web dependencies…"
  npm --prefix web ci --no-audit --no-fund
fi

if [ "$MODE" = "preview" ]; then
  echo "» Building production bundle…"
  npm --prefix web run build
  echo "» Starting preview server on http://localhost:5180/"
  exec npm --prefix web run preview
else
  echo "» Starting Vite dev server on http://localhost:5180/"
  exec npm --prefix web run dev
fi

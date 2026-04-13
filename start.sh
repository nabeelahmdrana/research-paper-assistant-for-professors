#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh — One-command launcher for Research Paper Assistant
#
# Usage:
#   ./start.sh
#   npm start           (same thing via package.json)
#
# What it does:
#   1. Creates a Python venv in backend/venv if it doesn't exist
#   2. Installs / updates backend + MCP server Python deps
#   3. Installs root and frontend Node deps if node_modules is missing
#   4. Starts Backend (FastAPI on :8000) and Frontend (Next.js on :3000)
#      concurrently — the MCP server is spawned on-demand by the backend
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${BLUE}[setup]${NC} $*"; }
success() { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[setup]${NC} $*"; }

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}   Research Paper Assistant — Starting up...  ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── 1. Python virtual environment ─────────────────────────────────────────────
VENV="$ROOT/backend/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

if [ ! -f "$PYTHON" ]; then
  info "Creating Python virtual environment at backend/venv ..."
  python3 -m venv "$VENV"
  success "Virtual environment created."
fi

# ── 2. Backend Python dependencies ────────────────────────────────────────────
BACKEND_HASH_FILE="$VENV/.backend_req_hash"
BACKEND_REQ_HASH=$(md5 -q "$ROOT/backend/requirements.txt" 2>/dev/null \
  || md5sum "$ROOT/backend/requirements.txt" | cut -d' ' -f1)

if [ ! -f "$BACKEND_HASH_FILE" ] || [ "$(cat "$BACKEND_HASH_FILE")" != "$BACKEND_REQ_HASH" ]; then
  info "Installing/updating backend Python dependencies..."
  "$PIP" install -r "$ROOT/backend/requirements.txt" --quiet --disable-pip-version-check
  echo "$BACKEND_REQ_HASH" > "$BACKEND_HASH_FILE"
  success "Backend dependencies installed."
else
  success "Backend dependencies up to date — skipped."
fi

# ── 3. MCP server Python dependencies ─────────────────────────────────────────
MCP_HASH_FILE="$VENV/.mcp_req_hash"
MCP_REQ_HASH=$(md5 -q "$ROOT/mcp-server/requirements.txt" 2>/dev/null \
  || md5sum "$ROOT/mcp-server/requirements.txt" | cut -d' ' -f1)

if [ ! -f "$MCP_HASH_FILE" ] || [ "$(cat "$MCP_HASH_FILE")" != "$MCP_REQ_HASH" ]; then
  info "Installing/updating MCP server dependencies..."
  "$PIP" install -r "$ROOT/mcp-server/requirements.txt" --quiet --disable-pip-version-check
  echo "$MCP_REQ_HASH" > "$MCP_HASH_FILE"
  success "MCP server dependencies installed."
else
  success "MCP server dependencies up to date — skipped."
fi

# ── 4. Root Node dependencies (concurrently) ──────────────────────────────────
if [ ! -d "$ROOT/node_modules" ]; then
  info "Installing root npm packages (concurrently)..."
  cd "$ROOT" && npm install --silent
  success "Root npm packages installed."
fi

# ── 5. Frontend Node dependencies ─────────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  info "Installing frontend npm packages..."
  cd "$ROOT/frontend" && npm install --silent
  cd "$ROOT"
  success "Frontend npm packages installed."
fi

# ── 6. Verify .env exists ─────────────────────────────────────────────────────
ENV_FILE="$ROOT/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
  warn ".env not found — copying from .env.example. Edit backend/.env and set ANTHROPIC_API_KEY."
  cp "$ROOT/backend/.env.example" "$ENV_FILE"
elif grep -q "your_anthropic_api_key_here" "$ENV_FILE"; then
  warn "ANTHROPIC_API_KEY is still a placeholder in backend/.env — the research pipeline won't work without it."
fi

# ── 7. Launch ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Backend  ${BLUE}→ http://localhost:8000${NC}"
echo -e "  Frontend ${GREEN}→ http://localhost:3000${NC}"
echo -e "  API docs ${BLUE}→ http://localhost:8000/docs${NC}"
echo -e "  MCP server: spawned on-demand by the backend"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cd "$ROOT"
exec npm run dev

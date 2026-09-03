#!/usr/bin/env bash
# KDD-Board Launcher (WebMCP, Blind Vault, Kanban UI)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOARD_DIR="$(cd "$REPO_DIR/.." && pwd)/kdd-board"

if [ ! -d "$BOARD_DIR" ]; then
  BOARD_DIR="$REPO_DIR/tools/kdd-board"
fi

if [ ! -d "$BOARD_DIR" ]; then
  echo "Error: no se encontró kdd-board en $BOARD_DIR"
  exit 1
fi

echo "🚀 Iniciando KDD-Board para el proyecto: $REPO_DIR"
cd "$BOARD_DIR"
export KDD_PROJECT_DIR="$REPO_DIR"
npm start

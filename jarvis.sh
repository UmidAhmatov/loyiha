#!/usr/bin/env bash
# jarvis.sh — setup.sh o'rnatgan OpenJarvis'ni ishga tushirish.
#
#   ./jarvis.sh              # suhbat
#   ./jarvis.sh gui          # grafik interfeys
#   ./jarvis.sh doctor       # holatni tekshirish
#   ./jarvis.sh <buyruq>...  # istalgan `jarvis` buyrug'i

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENJARVIS_DIR="${OPENJARVIS_DIR:-$SCRIPT_DIR/OpenJarvis}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if [[ ! -d "$OPENJARVIS_DIR/.venv" ]]; then
    echo "OpenJarvis o'rnatilmagan ($OPENJARVIS_DIR). Avval ./setup.sh ni ishga tushiring." >&2
    exit 1
fi

# Ollama o'rnatilgan, lekin ishlamayotgan bo'lsa — fonda ishga tushiramiz
if command -v ollama >/dev/null 2>&1 && ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    mkdir -p "$HOME/.openjarvis"
    nohup ollama serve > "$HOME/.openjarvis/ollama.log" 2>&1 &
    for _ in $(seq 1 30); do
        curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
        sleep 1
    done
fi

exec uv run --project "$OPENJARVIS_DIR" jarvis "$@"

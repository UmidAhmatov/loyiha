#!/usr/bin/env bash
# voice.sh — ElevenLabs ovozini boshqarish (avval: ./setup.sh --elevenlabs).
#
#   ./voice.sh key             # API kalitini kiritish yoki almashtirish (yashirin)
#   ./voice.sh voices          # akkauntingizdagi ovozlar ro'yxati (ID va nomi)
#   ./voice.sh voice <ID>      # Jarvis ovozini almashtirish
#   ./voice.sh test ["matn"]   # namuna yaratish (mp3 faylga)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENJARVIS_DIR="${OPENJARVIS_DIR:-$SCRIPT_DIR/OpenJarvis}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
el() { uv run --project "$OPENJARVIS_DIR" python -m openjarvis_elevenlabs "$@"; }

if [[ ! -d "$OPENJARVIS_DIR/.venv" ]] \
    || ! uv run --project "$OPENJARVIS_DIR" python -c "import openjarvis_elevenlabs" >/dev/null 2>&1; then
    echo "ElevenLabs moduli o'rnatilmagan. Avval: ./setup.sh --elevenlabs" >&2
    exit 1
fi

case "${1:-}" in
    key)
        el_key=""
        read -rsp "ElevenLabs API kaliti (yozganingiz ekranda ko'rinmaydi): " el_key || true
        echo
        printf '%s' "$el_key" | el save-key
        ;;
    voices) el voices ;;
    voice) [[ -n "${2:-}" ]] || usage; el configure "$2" ;;
    test) shift; el test "$@" ;;
    *) usage ;;
esac

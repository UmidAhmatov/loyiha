#!/usr/bin/env bash
# onec.sh — выручка из 1C (сначала: ./setup.sh --onec).
#
#   ./onec.sh login                          # ввести адрес OData, пользователя и пароль 1C
#   ./onec.sh check                          # проверить подключение
#   ./onec.sh revenue                        # выручка за текущий месяц
#   ./onec.sh revenue 01.09.2026 30.09.2026  # за период
#   ./onec.sh revenue 01.09.2026 30.09.2026 --by counterparty   # по контрагентам (или month, day)
#   ./onec.sh ask "Какая выручка за сентябрь?"                    # вопрос Jarvis с доступом к 1C

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENJARVIS_DIR="${OPENJARVIS_DIR:-$SCRIPT_DIR/OpenJarvis}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 2; }
onec() { uv run --project "$OPENJARVIS_DIR" python -m openjarvis_onec "$@"; }

if [[ ! -d "$OPENJARVIS_DIR/.venv" ]] \
    || ! uv run --project "$OPENJARVIS_DIR" python -c "import openjarvis_onec" >/dev/null 2>&1; then
    echo "Модуль 1C не установлен. Сначала: ./setup.sh --onec" >&2
    exit 1
fi

case "${1:-}" in
    login)
        onec_url="" onec_user="" onec_password=""
        read -rp "Адрес OData 1C (например http://сервер/база/odata/standard.odata): " onec_url || true
        read -rp "Пользователь 1C: " onec_user || true
        IFS= read -rsp "Пароль 1C (ввод не отображается): " onec_password || true
        echo
        printf '%s\n%s\n%s\n' "$onec_url" "$onec_user" "$onec_password" | onec save-credentials
        unset onec_password
        onec check
        ;;
    check) onec check ;;
    revenue) shift; onec revenue "$@" ;;
    ask)
        shift
        [[ $# -gt 0 ]] || usage
        exec "$SCRIPT_DIR/jarvis.sh" ask --agent orchestrator --tools onec_revenue "$@"
        ;;
    *) usage ;;
esac

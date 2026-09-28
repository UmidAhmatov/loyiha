#!/usr/bin/env bash
# setup.sh — OpenJarvis'ni manba kodidan (source checkout) o'rnatish.
#
# Linux, macOS va WSL2 (Windows ichidagi Ubuntu) uchun.
# Native Windows uchun README.md dagi PowerShell buyrug'idan foydalaning.
#
# Ishlatish:
#   ./setup.sh                      # hammasi: uv, Python paketlar, Rust kengaytma, Ollama, model
#   ./setup.sh --model qwen3.5:4b   # boshqa modelni yuklab olish
#   ./setup.sh --no-ollama          # Ollama o'rnatmaslik (masalan, bulutli API kaliti bilan ishlash uchun)
#   ./setup.sh --no-rust            # Rust kengaytmasini qurmaslik (xotira funksiyalari o'chadi)
#   ./setup.sh --dev                # dasturchi paketlari (pytest, ruff, pre-commit)
#
# Muhit o'zgaruvchilari:
#   OPENJARVIS_DIR       Kod qayerga klonlanadi (standart: shu skript yonidagi ./OpenJarvis)
#   OPENJARVIS_REPO_URL  Repo manzili (standart: https://github.com/open-jarvis/OpenJarvis.git)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENJARVIS_DIR="${OPENJARVIS_DIR:-$SCRIPT_DIR/OpenJarvis}"
OPENJARVIS_REPO_URL="${OPENJARVIS_REPO_URL:-https://github.com/open-jarvis/OpenJarvis.git}"
MODEL="qwen3.5:2b"
WITH_OLLAMA=1
WITH_RUST=1
WITH_DEV=0

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="${2:?--model uchun model nomi kerak}"; shift ;;
        --no-ollama) WITH_OLLAMA=0 ;;
        --no-rust) WITH_RUST=0 ;;
        --dev) WITH_DEV=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Noma'lum parametr: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[..]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[!!]${NC} $*"; }
die()  { echo -e "${RED}[xato]${NC} $*" >&2; exit 1; }

case "$(uname -s)" in
    Linux|Darwin) ;;
    MINGW*|MSYS*|CYGWIN*)
        die "Git Bash / MSYS2 qo'llab-quvvatlanmaydi. WSL2 (Ubuntu) ichida ishga tushiring yoki README.md dagi PowerShell usulidan foydalaning." ;;
    *) die "Qo'llab-quvvatlanmaydigan tizim: $(uname -s)" ;;
esac

for tool in git curl; do
    command -v "$tool" >/dev/null 2>&1 \
        || die "'$tool' topilmadi. O'rnating (Ubuntu: sudo apt install -y $tool; macOS: xcode-select --install) va qayta ishga tushiring."
done

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# 1. uv — Python paket menejeri (kerakli Python versiyasini ham o'zi yuklab oladi)
if command -v uv >/dev/null 2>&1; then
    ok "uv bor: $(uv --version)"
else
    info "uv o'rnatilmoqda..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    command -v uv >/dev/null 2>&1 || die "uv o'rnatildi, lekin PATH da topilmadi. Yangi terminal oching va qayta urinib ko'ring."
    ok "uv o'rnatildi: $(uv --version)"
fi

# 2. OpenJarvis kodini klonlash yoki yangilash
if [[ -d "$OPENJARVIS_DIR/.git" ]]; then
    info "OpenJarvis allaqachon bor ($OPENJARVIS_DIR) — yangilanmoqda..."
    git -C "$OPENJARVIS_DIR" pull --ff-only \
        || warn "git pull bajarilmadi (mahalliy o'zgarishlar bo'lishi mumkin) — mavjud kod bilan davom etamiz."
else
    info "OpenJarvis klonlanmoqda: $OPENJARVIS_DIR"
    # --filter=blob:none: tarix (teglar) saqlanadi, shuning uchun `jarvis --version` to'g'ri chiqadi
    git clone --filter=blob:none "$OPENJARVIS_REPO_URL" "$OPENJARVIS_DIR"
fi
ok "Kod tayyor: $OPENJARVIS_DIR"
cd "$OPENJARVIS_DIR"

# 3. Python paketlari (.venv ichiga)
extras=(--extra server)
# maturin (Rust kengaytmasini quruvchi) dev paketlari ichida
if [[ "$WITH_DEV" -eq 1 || "$WITH_RUST" -eq 1 ]]; then
    extras+=(--extra dev)
fi
info "Python paketlari o'rnatilmoqda (uv sync ${extras[*]})..."
uv sync "${extras[@]}"
ok "Python paketlari o'rnatildi: $(uv run jarvis --version)"

# 4. Rust kengaytmasi (xotira va xavfsizlik funksiyalari uchun)
if [[ "$WITH_RUST" -eq 1 ]]; then
    if ! command -v cargo >/dev/null 2>&1; then
        info "Rust (cargo) topilmadi — rustup orqali o'rnatilmoqda..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
    info "Rust kengaytmasi qurilmoqda (birinchi marta 3–10 daqiqa ketishi mumkin)..."
    if uv run maturin develop --release --manifest-path rust/crates/openjarvis-python/Cargo.toml \
        && uv run python -c "import openjarvis_rust" >/dev/null 2>&1; then
        ok "Rust kengaytmasi tayyor"
    else
        warn "Rust kengaytmasi qurilmadi. OpenJarvis ishlaydi, lekin xotira funksiyalari o'chiq bo'ladi."
        warn "Keyinroq qayta urinish: cd \"$OPENJARVIS_DIR\" && uv run maturin develop --release -m rust/crates/openjarvis-python/Cargo.toml"
    fi
else
    warn "--no-rust: Rust kengaytmasi o'tkazib yuborildi"
fi

# 5. Ollama — modelni mahalliy (kompyuterning o'zida) ishga tushiruvchi dvigatel
ollama_up() { curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; }

MODEL_READY=0
if [[ "$WITH_OLLAMA" -eq 1 ]]; then
    if command -v ollama >/dev/null 2>&1; then
        ok "Ollama bor"
    else
        info "Ollama o'rnatilmoqda..."
        case "$(uname -s)" in
            Linux) curl -fsSL https://ollama.com/install.sh | sh ;;
            Darwin)
                if command -v brew >/dev/null 2>&1; then
                    brew install ollama
                else
                    die "macOS da Ollama'ni https://ollama.com/download dan o'rnating va skriptni qayta ishga tushiring."
                fi ;;
        esac
    fi

    if ollama_up; then
        ok "Ollama ishlab turibdi"
    else
        info "Ollama ishga tushirilmoqda..."
        mkdir -p "$HOME/.openjarvis"
        nohup ollama serve > "$HOME/.openjarvis/ollama.log" 2>&1 &
        for _ in $(seq 1 60); do ollama_up && break; sleep 1; done
        ollama_up || die "Ollama ishga tushmadi. Log: $HOME/.openjarvis/ollama.log"
        ok "Ollama ishga tushdi"
    fi

    info "Model yuklab olinmoqda: $MODEL (bir necha GB bo'lishi mumkin)..."
    if ollama pull "$MODEL"; then
        MODEL_READY=1
        ok "Model tayyor: $MODEL"
    else
        warn "Model yuklanmadi. Keyinroq: ollama pull $MODEL"
    fi
else
    warn "--no-ollama: Ollama o'tkazib yuborildi"
fi

# 6. Konfiguratsiya (~/.openjarvis/config.toml). Mavjud bo'lsa, tegmaymiz.
CONFIG="${OPENJARVIS_HOME:-$HOME/.openjarvis}/config.toml"
if [[ -f "$CONFIG" ]]; then
    ok "Konfiguratsiya allaqachon bor: $CONFIG (o'zgartirilmadi)"
else
    info "Konfiguratsiya yozilmoqda: $CONFIG"
    # ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY / GOOGLE_API_KEY
    # o'rnatilgan bo'lsa, bulutli model tanlanadi; aks holda mahalliy Ollama.
    uv run jarvis _bootstrap --write-config --engine ollama --model "$MODEL" \
        --prefer-cloud-when-available
fi

# 7. Grafik interfeys (`jarvis gui`) uchun Node.js/npm — ixtiyoriy, faqat ogohlantiramiz
version_ge() { [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" == "$2" ]]; }
GUI_READY=0
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    node_v="$(node --version | sed 's/^v//')"
    npm_v="$(npm --version)"
    if ! version_ge "$node_v" "22.22"; then
        warn "GUI uchun Node.js 22.22+ kerak (sizda $node_v): https://nodejs.org"
    elif ! version_ge "$npm_v" "11.19.0" || version_ge "$npm_v" "12"; then
        warn "GUI uchun npm 11.19+ kerak (sizda $npm_v). Yangilash: npm install -g npm@11"
    else
        GUI_READY=1
        ok "Node.js $node_v / npm $npm_v — GUI ishlaydi"
    fi
else
    warn "Node.js topilmadi — GUI ishlamaydi (terminal rejimi ishlaydi). O'rnatish: https://nodejs.org (22.22+)"
fi

# 8. Tekshiruv
info "jarvis doctor ishga tushirilmoqda..."
uv run jarvis doctor || true

echo
echo -e "${GREEN}OpenJarvis o'rnatildi!${NC}"
echo
echo "Ishga tushirish:"
echo "  $SCRIPT_DIR/jarvis.sh              # terminalda suhbat"
if [[ "$GUI_READY" -eq 1 ]]; then
    echo "  $SCRIPT_DIR/jarvis.sh gui          # brauzerdagi grafik interfeys"
else
    echo "  $SCRIPT_DIR/jarvis.sh gui          # grafik interfeys (avval yuqoridagi Node.js/npm ogohlantirishini hal qiling)"
fi
echo "  $SCRIPT_DIR/jarvis.sh ask \"Salom!\" # bitta savol"
if [[ "$WITH_OLLAMA" -eq 1 && "$MODEL_READY" -ne 1 ]]; then
    echo
    warn "Model hali yuklanmagan — suhbatdan oldin: ollama pull $MODEL"
fi

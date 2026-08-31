#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${MANDACOR_BACKEND_PORT:-8000}"
EXPO_PORT="${MANDACOR_EXPO_PORT:-8081}"
BACKEND_PID=""
LOG_DIR="$PROJECT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"

on_exit() {
  local exit_code=$?
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo
    echo "Encerrando o backend MANDACOR..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap on_exit EXIT INT TERM

fail() {
  echo
  echo "ERRO: $1"
  echo "Pressione Enter para fechar."
  read -r || true
  exit 1
}

echo
echo "=========================================================="
echo "  MANDACOR - Inicializador Linux"
echo "=========================================================="
echo

command -v node >/dev/null 2>&1 || fail "Node.js não encontrado. Instale a versão LTS de https://nodejs.org/."
command -v npm >/dev/null 2>&1 || fail "npm não encontrado. Instale o Node.js LTS."

PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "[1/5] Preparando o Python..."
  command -v python3 >/dev/null 2>&1 || fail "Python 3.11 ou superior não encontrado."
  python3 -m venv "$PROJECT_DIR/.venv" || fail "Não foi possível criar o ambiente Python. Instale o pacote python3-venv."
fi

echo "[2/5] Verificando o backend..."
if ! "$PYTHON_EXE" -c 'import mandacor, fastapi, uvicorn' >/dev/null 2>&1; then
  echo "Instalando dependências do backend pela primeira vez..."
  "$PYTHON_EXE" -m pip install -e "$PROJECT_DIR" || fail "Falha ao instalar as dependências do backend."
fi

echo "[3/5] Verificando o aplicativo Expo..."
if [[ ! -x "$PROJECT_DIR/mobile/node_modules/.bin/expo" ]]; then
  (cd "$PROJECT_DIR/mobile" && npm ci) || fail "Falha ao instalar as dependências do aplicativo."
fi

if [[ -z "${MANDACOR_LAN_IP:-}" ]]; then
  if command -v ip >/dev/null 2>&1; then
    MANDACOR_LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([^ ]*\).*/\1/p' | head -n 1)"
  else
    MANDACOR_LAN_IP=""
  fi
fi
MANDACOR_LAN_IP="${MANDACOR_LAN_IP:-127.0.0.1}"
export EXPO_PUBLIC_MANDACOR_API_URL="http://$MANDACOR_LAN_IP:$BACKEND_PORT"
export EXPO_PUBLIC_MANDACOR_FORCE_API_URL=1

echo "[4/5] Iniciando API em $EXPO_PUBLIC_MANDACOR_API_URL ..."
mkdir -p "$LOG_DIR"
health_ready() {
  "$PYTHON_EXE" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$BACKEND_PORT/health', timeout=1).read()" >/dev/null 2>&1
}

if ! health_ready; then
  (
    cd "$PROJECT_DIR"
    exec "$PYTHON_EXE" -m mandacor api serve \
      --host 0.0.0.0 \
      --port "$BACKEND_PORT" \
      --cors-origin "http://localhost:$EXPO_PORT" \
      --cors-origin "http://127.0.0.1:$EXPO_PORT" \
      --cors-origin "http://$MANDACOR_LAN_IP:$EXPO_PORT"
  ) >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
fi

API_READY=""
for _attempt in {1..30}; do
  if health_ready; then
    API_READY=1
    break
  fi
  sleep 1
done
if [[ -z "$API_READY" ]]; then
  [[ -f "$BACKEND_LOG" ]] && tail -n 30 "$BACKEND_LOG"
  fail "O backend não respondeu. Consulte $BACKEND_LOG."
fi

echo "[5/5] Abrindo Expo..."
echo
echo "API do celular: $EXPO_PUBLIC_MANDACOR_API_URL"
echo "Leia o QR Code abaixo usando o Expo Go."
echo "Para encerrar tudo, pressione Ctrl+C."
echo

cd "$PROJECT_DIR/mobile"
npx expo start --lan --port "$EXPO_PORT"

#!/usr/bin/env bash
# Installs the MANDACOR backend as a systemd service that starts with the bench PC.
#
#   ./INSTALAR_SERVICO_LINUX.sh            install (or update) and start the service
#   ./INSTALAR_SERVICO_LINUX.sh --mostrar  print the unit file without installing
#   ./INSTALAR_SERVICO_LINUX.sh --remover  stop and remove the service
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${MANDACOR_BACKEND_PORT:-8000}"
SERVICE_NAME="mandacor"
UNIT_PATH="/etc/systemd/system/$SERVICE_NAME.service"
PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"
SERVICE_USER="${SUDO_USER:-$(id -un)}"

fail() {
  echo "ERRO: $1" >&2
  exit 1
}

unit_file() {
  cat <<EOF
[Unit]
Description=MANDACOR API (espectrofotômetro BYK)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_EXE -m mandacor api serve --host 0.0.0.0 --port $BACKEND_PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

case "${1:-}" in
  --mostrar)
    unit_file
    exit 0
    ;;
  --remover)
    sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
    sudo rm -f "$UNIT_PATH"
    sudo systemctl daemon-reload
    echo "Serviço MANDACOR removido."
    exit 0
    ;;
  "") ;;
  *) fail "opção desconhecida: $1 (use --mostrar ou --remover)" ;;
esac

command -v systemctl >/dev/null 2>&1 || fail "systemd não encontrado neste computador."

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "[1/4] Preparando o Python..."
  command -v python3 >/dev/null 2>&1 || fail "Python 3.11 ou superior não encontrado."
  python3 -m venv "$PROJECT_DIR/.venv" || fail "Não foi possível criar o ambiente Python. Instale o pacote python3-venv."
fi

echo "[2/4] Verificando as dependências do backend..."
if ! "$PYTHON_EXE" -c 'import mandacor, fastapi, uvicorn' >/dev/null 2>&1; then
  "$PYTHON_EXE" -m pip install -e "$PROJECT_DIR" || fail "Falha ao instalar as dependências do backend."
fi

echo "[3/4] Instalando o serviço (será pedida a senha de administrador)..."
unit_file | sudo tee "$UNIT_PATH" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "[4/4] Aguardando a API responder..."
for _attempt in {1..30}; do
  if "$PYTHON_EXE" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$BACKEND_PORT/health', timeout=1).read()" >/dev/null 2>&1; then
    LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([^ ]*\).*/\1/p' | head -n 1)"
    echo
    echo "MANDACOR está rodando e vai iniciar sozinho com o computador."
    echo "No aplicativo, em CONFIG, use o servidor: http://${LAN_IP:-IP_DO_PC}:$BACKEND_PORT"
    echo "Ver o log:   journalctl -u $SERVICE_NAME -f"
    exit 0
  fi
  sleep 1
done
sudo systemctl --no-pager status "$SERVICE_NAME" | tail -n 20 || true
fail "A API não respondeu. Veja o log com: journalctl -u $SERVICE_NAME -e"

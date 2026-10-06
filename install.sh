#!/usr/bin/env bash
# Instala passencryptenv: binarios en ~/.local/bin y el agente al inicio de sesión.
#
#   ./install.sh            -> autostart por .desktop (recomendado: entorno gráfico garantizado)
#   ./install.sh --systemd  -> servicio systemd --user (auto-reinicio, logs)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="$HOME/.config/autostart"
SYSTEMD_DIR="$HOME/.config/systemd/user"
UNIT_NAME="passencryptenv-agent.service"
MODE="desktop"

for arg in "$@"; do
    case "$arg" in
        --systemd) MODE="systemd" ;;
        -h|--help) echo "uso: ./install.sh [--systemd]"; exit 0 ;;
        *) echo "opción desconocida: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p "$BIN_DIR" "$AUTOSTART_DIR"
chmod +x "$REPO_DIR/bin/passenv" "$REPO_DIR/bin/passenv-agent" "$REPO_DIR/bin/passenv-load"

ln -sf "$REPO_DIR/bin/passenv" "$BIN_DIR/passenv"
ln -sf "$REPO_DIR/bin/passenv-agent" "$BIN_DIR/passenv-agent"
ln -sf "$REPO_DIR/bin/passenv-load" "$BIN_DIR/passenv-load"
echo "Enlazados: $BIN_DIR/{passenv,passenv-agent,passenv-load}"

if [ "$MODE" = "systemd" ]; then
    mkdir -p "$SYSTEMD_DIR"
    cp "$REPO_DIR/packaging/$UNIT_NAME" "$SYSTEMD_DIR/$UNIT_NAME"
    rm -f "$AUTOSTART_DIR/passenv-agent.desktop"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload || true
        systemctl --user enable --now "$UNIT_NAME" || true
    fi
    echo "systemd --user activado: $UNIT_NAME"
else
    sed "s|__PASSENV_AGENT__|$BIN_DIR/passenv-agent|" \
        "$REPO_DIR/packaging/passenv-agent.desktop" > "$AUTOSTART_DIR/passenv-agent.desktop"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
    fi
    echo "Autostart (.desktop) instalado: $AUTOSTART_DIR/passenv-agent.desktop"
fi

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "AVISO: añade $BIN_DIR al PATH para invocar 'passenv'." ;;
esac

echo
echo "Hecho. Pasos siguientes:"
echo "  1) passenv init        # crea bóveda + TOTP + clave de recuperación"
echo "  2) cierra y abre sesión (o: passenv-agent --delay 0 --no-popup &)"
echo "  3) passenv status"

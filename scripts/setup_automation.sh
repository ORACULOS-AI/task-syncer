#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Configurando Automação de Sincronização Jira (task-syncer)...${NC}"

# Define o root do repo como o diretório pai da pasta de scripts
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

SYSTEMD_DIR="$HOME/.config/systemd/user"
STATE_DIR="$HOME/.task-syncer"

# Garante que as pastas existam
mkdir -p "$SYSTEMD_DIR"
mkdir -p "$STATE_DIR"

# 1. Criar o arquivo de serviço (uso de caminhos dinâmicos)
cat <<EOF > "$SYSTEMD_DIR/jira-sync.service"
[Unit]
Description=Sincronizacao Automatica do Jira (task-syncer)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$(which python3) $SCRIPT_DIR/full_jira_sync.py
WorkingDirectory=$PROJECT_ROOT
StandardOutput=append:$STATE_DIR/sync.log
StandardError=append:$STATE_DIR/sync.log

[Install]
WantedBy=default.target
EOF

# 2. Criar o arquivo de timer
cat <<EOF > "$SYSTEMD_DIR/jira-sync.timer"
[Unit]
Description=Roda o sync do Jira a cada 30 minutos

[Timer]
OnCalendar=*:0,30
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 3. Recarregar e ativar
systemctl --user daemon-reload
systemctl --user enable jira-sync.timer
systemctl --user start jira-sync.timer

# 4. Injeção Automática (path relativo)
HOOK_CODE="
# --- TASK-SYNCER JIRA SYNC HOOK ---
function _jira_sync_on_terminal() {
    local last_sync=\"\$HOME/.task-syncer/last_sync_timestamp\"
    local now=\$(date +%s)
    local threshold=600 # 10 minutos
    
    if [[ ! -f \"\$last_sync\" || \$((now - \$(cat \"\$last_sync\"))) -gt \$threshold ]]; then
        (systemctl --user start jira-sync.service &)
    fi
}
_jira_sync_on_terminal
# -------------------------------
"

inject_hook() {
    local file="$1"
    if [ -f "$file" ]; then
        if ! grep -q "_jira_sync_on_terminal" "$file"; then
            echo -e "${BLUE}📝 Injetando hook em $file...${NC}"
            echo "$HOOK_CODE" >> "$file"
        fi
    fi
}

inject_hook "$HOME/.zshrc"
inject_hook "$HOME/.bashrc"

echo -e "${GREEN}✅ Automação 100% configurada e ativa!${NC}"
echo -e "• Caminho base: $PROJECT_ROOT"
echo -e "\nReinicie seu terminal para ativar o hook."

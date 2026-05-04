#!/usr/bin/env python3
import sys
import os
import subprocess

# --- Configurações básicas ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Adiciona o diretório atual ao sys.path para importar os módulos
sys.path.append(BASE_DIR)

def run_sync():
    print("🚀 Executando sincronização completa...")
    # Importa o módulo de sync (agora está em scripts/full_jira_sync.py)
    from scripts import full_jira_sync
    full_jira_sync.main()

def run_setup():
    print("🔧 Iniciando configuração da automação do sistema...")
    setup_script = os.path.join(BASE_DIR, "scripts", "setup_automation.sh")
    if os.path.exists(setup_script):
        subprocess.run(["bash", setup_script])
    else:
        print(f"Erro: Script de setup não encontrado em {setup_script}")

def print_help():
    print("""
Task Syncer - CLI da ORACULOS

Uso:
  ./task-syncer.py sync    - Executa a sincronização completa do Jira
  ./task-syncer.py setup   - Configura o systemd e hooks de terminal
  ./task-syncer.py help    - Mostra esta ajuda
""")

def main():
    if len(sys.argv) < 2:
        print_help()
        return
        
    cmd = sys.argv[1].lower()
    
    if cmd == "sync":
        run_sync()
    elif cmd == "setup":
        run_setup()
    elif cmd == "help":
        print_help()
    else:
        print(f"Comando desconhecido: {cmd}")
        print_help()

if __name__ == "__main__":
    main()

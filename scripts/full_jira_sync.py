import json
import os
import requests
from requests.auth import HTTPBasicAuth

# Tenta carregar do .env se a biblioteca python-dotenv estiver instalada
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# --- CONFIGURAÇÃO ---
# Obtém o diretório do script para definir caminhos relativos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JIRA_URL = os.getenv("JIRA_URL", "https://your-domain.atlassian.net").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "").strip()
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "_sync").strip()


def discover_projects():
    """Descobre automaticamente todos os projetos acessíveis no espaço Jira."""
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/project/search?maxResults=100"

    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code != 200:
        print(f"Erro ao descobrir projetos: {response.status_code} - {response.text}")
        return {}

    projects = {}
    for p in response.json().get("values", []):
        key = p["key"]
        name = p["name"]
        # Remove prefixo "[KEY] " que o Jira às vezes inclui no nome
        import re

        clean_name = re.sub(r"^\[[A-Z0-9]+\]\s*", "", name).strip()
        projects[key] = {
            "name": clean_name,
            "path": os.path.join(BASE_DIR, OUTPUT_DIR, clean_name),
        }
        print(f"  → Projeto encontrado: {key} — {name}")
    return projects


# Campos de interesse para extração de dados
# customfield_10020: Sprint
# customfield_10016: Story Point Estimate
FIELDS = [
    "priority",
    "status",
    "summary",
    "issuetype",
    "created",
    "parent",
    "customfield_10020",
    "customfield_10016",
    "description",
    "assignee",
    "reporter",
    "labels",
]


def fetch_all_issue_ids(project_key):
    """Busca todos os IDs de issues de um projeto usando paginação."""
    print(f"\n[1/3] Buscando todos os IDs de issues para {project_key}...")
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/search/jql"

    all_ids = []
    next_token = None

    while True:
        payload = {
            "jql": f"project = {project_key} ORDER BY created DESC",
            "maxResults": 100,
        }
        if next_token:
            payload["nextPageToken"] = next_token

        response = requests.post(url, headers=headers, json=payload, auth=auth)
        if response.status_code != 200:
            print(f"Erro na busca JQL: {response.status_code} - {response.text}")
            break

        data = response.json()
        issues = data.get("issues", [])
        all_ids.extend([i["id"] for i in issues])

        next_token = data.get("nextPageToken")
        if not next_token or data.get("isLast"):
            break

    print(f"Encontrados {len(all_ids)} itens.")
    return all_ids


def fetch_issue_details(issue_ids):
    """Busca detalhes das issues em lotes (Bulk Fetch)."""
    print(f"[2/3] Buscando detalhes de {len(issue_ids)} issues...")
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/issue/bulkfetch"

    all_details = []
    # Lotes de 100 para evitar timeout/limites
    for i in range(0, len(issue_ids), 100):
        batch = issue_ids[i : i + 100]
        payload = {"issueIdsOrKeys": batch, "fields": FIELDS}
        response = requests.post(url, headers=headers, json=payload, auth=auth)
        if response.status_code == 200:
            all_details.extend(response.json().get("issues", []))
            print(f"  ... processados {len(all_details)}/{len(issue_ids)}")
        else:
            print(f"Erro no Bulk Fetch lote {i}: {response.status_code}")

    return all_details


def parse_sprint(issue):
    """Extrai informações da sprint do campo customfield_10020."""
    sprints = issue.get("fields", {}).get("customfield_10020")
    if not sprints or not isinstance(sprints, list) or len(sprints) == 0:
        return None
    # Prioriza a sprint ativa, caso contrário a última (planejada)
    active = [s for s in sprints if s.get("state") == "active"]
    if active:
        return active[0]
    return sprints[-1]


def adf_to_markdown(node, depth=0):
    """Converte ADF (Atlassian Document Format) para texto markdown legível."""
    if not node or not isinstance(node, dict):
        return ""

    ntype = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    if ntype == "text":
        result = text
        marks = node.get("marks", [])
        for mark in marks:
            mt = mark.get("type", "")
            if mt == "strong":
                result = f"**{result}**"
            elif mt == "em":
                result = f"*{result}*"
            elif mt == "code":
                result = f"`{result}`"
            elif mt == "link":
                href = mark.get("attrs", {}).get("href", "")
                result = f"[{result}]({href})"
        return result

    parts = [adf_to_markdown(c, depth) for c in content]
    joined = "".join(parts)

    if ntype == "doc":
        return joined
    elif ntype == "paragraph":
        return joined.strip() + "\n\n" if joined.strip() else ""
    elif ntype in ("heading",):
        level = node.get("attrs", {}).get("level", 2)
        return f"{'#' * level} {joined.strip()}\n\n"
    elif ntype == "bulletList":
        return joined
    elif ntype == "orderedList":
        return joined
    elif ntype == "listItem":
        return f"- {joined.strip()}\n"
    elif ntype == "codeBlock":
        lang = node.get("attrs", {}).get("language", "")
        return f"```{lang}\n{joined.strip()}\n```\n\n"
    elif ntype == "blockquote":
        lines = joined.strip().split("\n")
        return "\n".join(f"> {l}" for l in lines) + "\n\n"
    elif ntype == "hardBreak":
        return "\n"
    elif ntype == "rule":
        return "---\n\n"
    elif ntype == "inlineCard":
        url = node.get("attrs", {}).get("url", "")
        return f"[{url}]({url})"
    elif ntype == "panel":
        panel_type = node.get("attrs", {}).get("panelType", "info").upper()
        return f"**[{panel_type}]** {joined.strip()}\n\n"
    else:
        return joined


def generate_issues_folder(project_key, issues, path):
    """Gera pasta ISSUES/ com um .md por issue, organizada por status."""
    issues_root = os.path.join(path, "ISSUES")

    # Limpa a pasta completamente para garantir sincronização fiel
    import shutil

    if os.path.exists(issues_root):
        shutil.rmtree(issues_root)
    os.makedirs(issues_root, exist_ok=True)

    for issue in issues:
        fields = issue.get("fields", {})
        itype = fields.get("issuetype", {}).get("name", "")
        key = issue.get("key", "N/A")
        summary = fields.get("summary", "N/A")
        status = fields.get("status", {}).get("name", "Sem Status")
        priority = (
            fields.get("priority", {}).get("name", "-")
            if fields.get("priority")
            else "-"
        )
        points = fields.get("customfield_10016", "-")
        created = fields.get("created", "")[:10]
        assignee_obj = fields.get("assignee")
        assignee = assignee_obj.get("displayName", "-") if assignee_obj else "-"
        reporter_obj = fields.get("reporter")
        reporter = reporter_obj.get("displayName", "-") if reporter_obj else "-"
        labels = fields.get("labels", [])
        parent = fields.get("parent")
        parent_str = (
            f"{parent.get('key')}: {parent.get('fields', {}).get('summary', '')}"
            if parent
            else "-"
        )

        sprint = parse_sprint(issue)
        sprint_str = sprint.get("name", "-") if sprint else "-"

        description_adf = fields.get("description")
        if description_adf and isinstance(description_adf, dict):
            description_md = adf_to_markdown(description_adf).strip()
        elif description_adf and isinstance(description_adf, str):
            description_md = description_adf.strip()
        else:
            description_md = "*Sem descrição.*"

        # Cria subpasta por status
        status_dir = os.path.join(issues_root, status)
        os.makedirs(status_dir, exist_ok=True)

        lines = [
            f"# {key}: {summary}",
            "",
            f"**Status:** {status}  ",
            f"**Tipo:** {itype}  ",
            f"**Prioridade:** {priority}  ",
            f"**Pontos:** {points}  ",
            f"**Sprint:** {sprint_str}  ",
            f"**Responsável:** {assignee}  ",
            f"**Reporter:** {reporter}  ",
            f"**Criado em:** {created}  ",
            f"**Epic/Parent:** {parent_str}  ",
        ]
        if labels:
            lines.append(f"**Labels:** {', '.join(labels)}  ")
        lines += ["", "---", "", "## Descrição", "", description_md, ""]

        with open(os.path.join(status_dir, f"{key}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # Gera índice resumido ISSUES/README.md
    status_counts = {}
    for issue in issues:
        st = issue.get("fields", {}).get("status", {}).get("name", "Sem Status")
        status_counts[st] = status_counts.get(st, 0) + 1

    with open(os.path.join(issues_root, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# Issues — {project_key}\n\n")
        f.write(
            "Cada issue tem seu próprio `.md` dentro da pasta do status correspondente.\n\n"
        )
        f.write("| Status | Quantidade |\n| :--- | :---: |\n")
        for st, count in sorted(status_counts.items()):
            f.write(f"| {st} | {count} |\n")


def generate_markdown_table(issues):
    if not issues:
        return "*Nenhum item encontrado.*\n"

    table = "| Key | Summary | Status | Type | Responsável | Points | Created |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    for issue in issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "N/A")
        summary = fields.get("summary", "N/A").replace("|", "\\|")
        status = fields.get("status", {}).get("name", "N/A")
        itype = fields.get("issuetype", {}).get("name", "N/A")
        assignee_obj = fields.get("assignee")
        assignee = assignee_obj.get("displayName", "-") if assignee_obj else "-"
        points = fields.get("customfield_10016", "-")
        created = fields.get("created", "")[:10]
        table += f"| {key} | {summary} | {status} | {itype} | {assignee} | {points} | {created} |\n"
    return table


def organize_and_save(project_key, issues, projects):
    info = projects[project_key]
    path = info["path"]
    os.makedirs(path, exist_ok=True)
    print(f"[3/3] Organizando arquivos em {path}...")

    # Salva JSON completo para backup técnico
    with open(os.path.join(path, "data.json"), "w", encoding="utf-8") as f:
        json.dump({"issues": issues}, f, indent=2, ensure_ascii=False)

    # 1. Agrupamento por Sprint / Backlog
    active_sprints = {}
    future_sprints = {}
    backlog = []

    for issue in issues:
        itype = issue.get("fields", {}).get("issuetype", {}).get("name")
        if itype == "Epic":
            continue  # Epics não vão para sprints da mesma forma

        sprint = parse_sprint(issue)
        if sprint:
            s_name = sprint.get("name", "Unknown Sprint")
            s_state = sprint.get("state")
            if s_state == "active":
                if s_name not in active_sprints:
                    active_sprints[s_name] = []
                active_sprints[s_name].append(issue)
            else:
                if s_name not in future_sprints:
                    future_sprints[s_name] = []
                future_sprints[s_name].append(issue)
        else:
            backlog.append(issue)

    # 2. Geração do BOARD.md
    with open(os.path.join(path, "BOARD.md"), "w", encoding="utf-8") as f:
        f.write(f"# Board - {info['name']} ({project_key})\n\n")
        f.write(
            "Este arquivo mostra as tarefas planejadas para execução imediata ou futura.\n\n"
        )

        if not active_sprints:
            f.write("## 🏃 Current Sprint\n*Sem sprint ativa no momento.*\n\n")
        else:
            for s_name, s_issues in active_sprints.items():
                f.write(f"## 🏃 Current Sprint: {s_name}\n")
                f.write(generate_markdown_table(s_issues))
                f.write("\n")

        if future_sprints:
            f.write("## 📅 Future Sprints\n")
            for s_name, s_issues in future_sprints.items():
                f.write(f"### {s_name}\n")
                f.write(generate_markdown_table(s_issues))
                f.write("\n")

    # 3. Geração do BACKLOG.md
    with open(os.path.join(path, "BACKLOG.md"), "w", encoding="utf-8") as f:
        f.write(f"# Backlog - {info['name']} ({project_key})\n\n")
        f.write("Itens que ainda não foram alocados em nenhuma sprint.\n\n")
        f.write(generate_markdown_table(backlog))

    # 4. Geração do EPICS.md (Hierarquia)
    epics = [
        i
        for i in issues
        if i.get("fields", {}).get("issuetype", {}).get("name") == "Epic"
    ]
    stories = [
        i
        for i in issues
        if i.get("fields", {}).get("issuetype", {}).get("name") != "Epic"
        and not i.get("fields", {}).get("issuetype", {}).get("subtask")
    ]
    subtasks = [
        i for i in issues if i.get("fields", {}).get("issuetype", {}).get("subtask")
    ]

    # Mapear filhos para pais
    parent_map = {}
    for item in stories + subtasks:
        parent = item.get("fields", {}).get("parent")
        if parent:
            p_key = parent.get("key")
            if p_key not in parent_map:
                parent_map[p_key] = []
            parent_map[p_key].append(item)

    with open(os.path.join(path, "EPICS.md"), "w", encoding="utf-8") as f:
        f.write(f"# Hierarchy - {info['name']} ({project_key})\n\n")
        f.write("Visão estrutural de grandes entregas e seus desdobramentos.\n\n")

        for epic in epics:
            e_key = epic["key"]
            e_sum = epic["fields"]["summary"]
            status = epic.get("fields", {}).get("status", {}).get("name", "N/A")
            f.write(f"## 🏆 {e_key}: {e_sum} `[{status}]`\n")

            epic_stories = parent_map.get(e_key, [])
            if not epic_stories:
                f.write("*Sem histórias vinculadas.*\n")
            else:
                for story in epic_stories:
                    s_key = story["key"]
                    s_sum = story["fields"]["summary"]
                    s_status = (
                        story.get("fields", {}).get("status", {}).get("name", "N/A")
                    )
                    s_assignee_obj = story.get("fields", {}).get("assignee")
                    s_assignee = (
                        s_assignee_obj.get("displayName", "-")
                        if s_assignee_obj
                        else "-"
                    )
                    f.write(
                        f"- 📘 **{s_key}**: {s_sum} `({s_status})` — 👤 {s_assignee}\n"
                    )

                    story_subs = parent_map.get(s_key, [])
                    for sub in story_subs:
                        sub_key = sub["key"]
                        sub_sum = sub["fields"]["summary"]
                        sub_status = (
                            sub.get("fields", {}).get("status", {}).get("name", "N/A")
                        )
                        sub_assignee_obj = sub.get("fields", {}).get("assignee")
                        sub_assignee = (
                            sub_assignee_obj.get("displayName", "-")
                            if sub_assignee_obj
                            else "-"
                        )
                        f.write(
                            f"    - 🛠️ {sub_key}: {sub_sum} `({sub_status})` — 👤 {sub_assignee}\n"
                        )
            f.write("\n")

        # Stories sem Epic
        epic_keys = [e["key"] for e in epics]
        orphan_stories = [
            s
            for s in stories
            if not s.get("fields", {}).get("parent")
            or s.get("fields", {}).get("parent", {}).get("key") not in epic_keys
        ]

        if orphan_stories:
            f.write("## 📄 Stories outside Epics\n")
            for story in orphan_stories:
                o_assignee_obj = story.get("fields", {}).get("assignee")
                o_assignee = (
                    o_assignee_obj.get("displayName", "-") if o_assignee_obj else "-"
                )
                f.write(
                    f"- 📘 **{story['key']}**: {story['fields']['summary']} — 👤 {o_assignee}\n"
                )
                story_subs = parent_map.get(story["key"], [])
                for sub in story_subs:
                    sub_assignee_obj = sub.get("fields", {}).get("assignee")
                    sub_assignee = (
                        sub_assignee_obj.get("displayName", "-")
                        if sub_assignee_obj
                        else "-"
                    )
                    f.write(
                        f"    - 🛠️ {sub['key']}: {sub['fields']['summary']} — 👤 {sub_assignee}\n"
                    )

    # 5. Geração da pasta ISSUES/
    generate_issues_folder(project_key, issues, path)


def main():
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        print(
            "Erro: JIRA_EMAIL e JIRA_API_TOKEN devem estar definidos no ambiente ou no arquivo .env."
        )
        return

    print(f"🔍 Descobrindo projetos em {JIRA_URL}...")
    projects = discover_projects()
    if not projects:
        print("Nenhum projeto encontrado. Verifique as credenciais e a URL.")
        return

    if JIRA_PROJECT_KEY:
        if JIRA_PROJECT_KEY not in projects:
            print(
                f"Erro: Projeto '{JIRA_PROJECT_KEY}' não encontrado. Projetos disponíveis: {', '.join(projects.keys())}"
            )
            return
        keys_to_sync = [JIRA_PROJECT_KEY]
    else:
        keys_to_sync = list(projects.keys())

    print(f"\n🚀 Iniciando sincronização de {len(keys_to_sync)} projeto(s)...")
    for key in keys_to_sync:
        ids = fetch_all_issue_ids(key)
        if ids:
            details = fetch_issue_details(ids)
            organize_and_save(key, details, projects)
        else:
            print(f"Aviso: Nenhuma issue encontrada para o projeto {key}.")

    print(f"\n✅ Sincronização concluída com sucesso para todos os projetos!")

    try:
        import time

        timestamp_dir = os.path.expanduser("~/.task-syncer")
        os.makedirs(timestamp_dir, exist_ok=True)
        with open(os.path.join(timestamp_dir, "last_sync_timestamp"), "w") as f:
            f.write(str(int(time.time())))
    except Exception as e:
        print(f"Erro ao salvar timestamp: {e}")


if __name__ == "__main__":
    main()

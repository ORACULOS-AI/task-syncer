# task-syncer

A CLI tool to sync Jira project data into local Markdown files, organized by project and sprint.

## Features

- Syncs Jira issues, sprints, epics, and backlog to local `.md` files
- Generates hierarchical views: Epic → Story → Task
- One `.md` file per issue with full metadata and description
- Supports multiple Jira projects simultaneously
- Filter by a single project via `JIRA_PROJECT_KEY` env var
- Automation via Systemd or terminal hooks

## Installation

```bash
pip install requests python-dotenv
```

Create a `.env` file in the repository root:

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token

# Optional: sync only one project (leave empty to sync all)
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

## Usage

```bash
./task-syncer.py sync    # Run a manual sync (auto-discovers all projects)
./task-syncer.py setup   # Configure automation (Systemd / terminal hook)
./task-syncer.py help    # Show help
```

## Output Structure

Each Jira project gets its own folder:

```
<Project Name>/
├── BOARD.md       # Active and future sprints (table format)
├── BACKLOG.md     # Issues not yet assigned to a sprint
├── EPICS.md       # Hierarchy tree: Epic > Story > Task
├── ISSUES/        # One .md per issue, organized by status
└── data.json      # Raw API data
```

## Using the Output in Another Project

The synced Markdown files work great as **living documentation** inside your main codebase.
Instead of copying files, create a **symlink** from your project to the generated folder:

```bash
# From your project root
ln -s /path/to/task-syncer/"Desenvolvimento B2B" docs/tasks
```

Now `docs/tasks/BOARD.md`, `docs/tasks/EPICS.md`, etc. are always up to date
after every sync — no manual copying, no stale docs.

Add the symlink target to your project's `.gitignore` so each developer points
to their own local copy of task-syncer.

## Project Structure

```
.
├── task-syncer.py   # Main CLI entry point
├── scripts/         # Sync logic and automation helpers
├── .env             # Jira credentials (gitignored)
└── <Project Name>/  # One folder per Jira project (auto-discovered)
```

## Automation

Run `./task-syncer.py setup` to install:

- A **Systemd timer** that syncs every 30 minutes
- A **terminal hook** that syncs when you open your shell (if >10 min since last sync)

## License

MIT

# task-syncer

A CLI tool to sync Jira project data into local Markdown files, organized by project and sprint.

## Features

- Syncs Jira issues, sprints, epics, and backlog to local `.md` files
- Generates hierarchical views: Epic → Story → Task
- One `.md` file per issue with full metadata and description
- Supports multiple Jira projects simultaneously
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
```

## Usage

```bash
./task-syncer.py sync    # Run a manual sync
./task-syncer.py setup   # Configure automation (Systemd / terminal hook)
./task-syncer.py help    # Show help
```

## Output Structure

Each configured Jira project gets its own folder:

```
<PROJECT_KEY>/
├── BOARD.md       # Active and future sprints (table format)
├── BACKLOG.md     # Issues not yet assigned to a sprint
├── EPICS.md       # Hierarchy tree: Epic > Story > Task
├── ISSUES/        # One .md per issue, organized by status
└── data.json      # Raw API data
```

## Project Structure

```
.
├── task-syncer.py   # Main CLI entry point
├── scripts/         # Sync logic and automation helpers
└── <PROJECT>/       # One folder per Jira project key
```

## Configuration

Map your Jira project keys to local folders inside `scripts/full_jira_sync.py`:

```python
PROJECT_MAP = {
    "MYPROJECT": "my-project/",
    "ANOTHER":   "another/",
}
```

## License

MIT

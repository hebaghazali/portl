# Portl

**Portl** is a developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.
Instead of writing one-off SQL or Python scripts for every migration, Portl gives you an **interactive wizard** and **YAML job configs** you can re-run, share, and version-control.

*Portl turns migrations into a repeatable, reliable system — not a grind.*

---

## Features

* Sources: Postgres, MySQL, CSV, Google Sheets.
* Interactive wizard — no need to remember 12 flags.
* YAML job specs — portable, reusable, version-controlled.
* Hooks — run scripts or APIs before/after rows or batches.
* Dry run + schema validation.
* Batch execution with retries.

---

## Installation

### Option 1: Docker (Recommended)

**Quick Start:**
```bash
# Run directly with Docker
docker run --rm ghcr.io/hebaghazali/portl:latest --help

# Install wrapper for native-like experience
# Linux/macOS/WSL:
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash

# Windows PowerShell:
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression

# Then run:
portl --help
```

**Direct Docker Usage:**
```bash
# Basic usage
docker run --rm ghcr.io/hebaghazali/portl:latest init

# With volume mounting for file access
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml

# With environment variables
docker run --rm -e PORTL_API_KEY=your_key ghcr.io/hebaghazali/portl:latest run jobs/sheets_to_db.yaml

# With custom config directory
docker run --rm -v "$PWD:/work" -v "$HOME/.portl:/home/app/.portl" ghcr.io/hebaghazali/portl:latest init
```

**Wrapper Installation:**
The wrapper script provides a native CLI experience while using Docker under the hood:
- Mounts current directory as `/work`
- Passes through `PORTL_*` environment variables
- Handles TTY detection for interactive commands
- Automatically pulls the latest image

### Option 2: Python Package

```bash
pip install portl
```

---

## Quickstart

### 1. Start a New Migration

```bash
portl init
```

This launches the wizard and asks questions like:

* What's your source? (Postgres/MySQL/CSV/Google Sheet)
* What's your destination?
* How do you want to map fields?
* Conflict strategy? (skip/overwrite/merge/fail)
* Any hooks before/after rows or batches?

At the end, Portl generates a **YAML job file** for you.

---

### 2. Example YAML Job

```yaml
source:
  type: csv
  path: ./data/users.csv
destination:
  type: postgres
  host: localhost
  database: mydb
  table: users
conflict: overwrite
batch_size: 100
hooks:
  before_batch: ./scripts/notify_start.sh
  after_batch: ./scripts/notify_done.sh
```

---

### 3. Run the Migration

```bash
portl run jobs/users_to_pg.yaml
```

---

### 4. Dry Run Preview

```bash
portl run jobs/users_to_pg.yaml --dry-run
```

→ Shows sample rows, schema mapping, and a row count check without writing data.

---

## Docker Distribution

Portl is distributed as a multi-architecture Docker image supporting both `linux/amd64` and `linux/arm64` platforms.

### Image Tags

- `ghcr.io/hebaghazali/portl:latest` - Latest stable release
- `ghcr.io/hebaghazali/portl:v0.2.0` - Specific version (replace with actual version)
- `ghcr.io/hebaghazali/portl:main` - Latest from main branch

### Platform Support

- ✅ **Linux AMD64** - Native support
- ✅ **Linux ARM64** - Native support (Apple Silicon, ARM servers)
- ✅ **macOS** - Via Docker Desktop (both Intel and Apple Silicon)
- ✅ **Windows** - Via Docker Desktop (PowerShell, CMD, Git Bash, WSL2)

### Advanced Usage

**Environment File:**
```bash
# Create .env file with your configuration
echo "PORTL_API_KEY=your_key" > .env
echo "PORTL_DB_HOST=localhost" >> .env

# Use with Docker
docker run --rm --env-file .env -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

**Network Access:**
```bash
# Access host services (useful for local databases)
docker run --rm --add-host host.docker.internal:host-gateway -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/local_db.yaml
```

**Custom Image:**
```bash
# Linux/macOS/WSL:
export PORTL_IMAGE=ghcr.io/hebaghazali/portl:v0.2.0
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash

# Windows PowerShell:
$env:PORTL_IMAGE="ghcr.io/hebaghazali/portl:v0.2.0"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
```

**Windows-Specific Usage:**
```powershell
# PowerShell
docker run --rm ghcr.io/hebaghazali/portl:latest --help

# With volume mounting (PowerShell)
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest init

# With volume mounting (CMD)
docker run --rm -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest init

# With environment variables (PowerShell)
docker run --rm -e PORTL_API_KEY=your_key ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

### Building from Source

```bash
# Build locally
make build

# Build multi-architecture
make build-multi

# Run tests
make test

# Create release
make release TAG=v1.0.0
```

## Documentation

See full docs & examples at: [coming soon]

---

## Contributing

We welcome issues, forks, and pull requests. MIT licensed.

---

With Portl, you'll **never write the same migration script twice.**

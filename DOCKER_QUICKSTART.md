# Portl Docker Quick Start

Get up and running with Portl in under 2 minutes using Docker.

## 🚀 Quick Start

### Option 1: One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
portl --help
```

This installs a wrapper that makes `portl` work like a native command while using Docker under the hood.

### Option 2: Direct Docker Usage

```bash
# Run portl directly with Docker
docker run --rm ghcr.io/hebaghazali/portl:latest --help

# Create your first migration
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

## 📋 Prerequisites

- **Docker Desktop** installed and running
- **Internet connection** for pulling images
- **Git** (optional, for version control)

### Install Docker Desktop

- **Windows:** Download from [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/)
- **macOS:** Download from [Docker Desktop for Mac](https://docs.docker.com/desktop/mac/install/)
- **Linux:** Follow [Docker Engine installation guide](https://docs.docker.com/engine/install/)

## 🎯 Your First Migration

### 1. Start the Wizard

```bash
# Using wrapper (if installed)
portl init

# Or using Docker directly
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

### 2. Follow the Interactive Prompts

The wizard will ask you:
- **Source type:** CSV, Postgres, MySQL, or Google Sheets
- **Destination type:** Where to send the data
- **Field mapping:** How to map columns
- **Conflict strategy:** What to do with duplicates
- **Batch size:** How many rows to process at once

### 3. Run Your Migration

```bash
# Using wrapper
portl run migration.yaml

# Or using Docker
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest run migration.yaml
```

## 🔧 Common Use Cases

### CSV to Database

```bash
# Create migration config
portl init

# Run migration
portl run jobs/csv_to_db.yaml
```

### Database to Database

```bash
# Create migration config
portl init

# Run migration with environment variables
docker run --rm \
  -v "$PWD:/work" -w /work \
  -e PORTL_SOURCE_DB_HOST=source-host \
  -e PORTL_DEST_DB_HOST=dest-host \
  ghcr.io/hebaghazali/portl:latest run jobs/db_to_db.yaml
```

### Google Sheets to Database

```bash
# Set up API credentials
export PORTL_GOOGLE_CREDENTIALS_FILE="/path/to/credentials.json"

# Create migration config
portl init

# Run migration
portl run jobs/sheets_to_db.yaml
```

## 🐳 Docker-Specific Features

### Volume Mounting

Mount your current directory to access files:

```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

### Environment Variables

Pass configuration via environment variables:

```bash
docker run --rm \
  -e PORTL_API_KEY=your_key \
  -e PORTL_DB_PASSWORD=secret \
  ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

### Environment Files

Use `.env` files for configuration:

```bash
# Create .env file
echo "PORTL_API_KEY=your_key" > .env
echo "PORTL_DB_HOST=localhost" >> .env

# Use with Docker
docker run --rm --env-file .env -v "$PWD:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

### Network Access

Access host services (useful for local databases):

```bash
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -v "$PWD:/work" -w /work \
  ghcr.io/hebaghazali/portl:latest run jobs/local_db.yaml
```

## 🔄 Updating Portl

### Update Wrapper

```bash
# Re-run the install script
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
```

### Update Docker Image

```bash
# Pull latest image
docker pull ghcr.io/hebaghazali/portl:latest

# Or pull specific version
docker pull ghcr.io/hebaghazali/portl:v0.2.0
```

## 🏷️ Version Pinning

For production use, pin to specific versions:

```bash
# Use specific version
docker run --rm ghcr.io/hebaghazali/portl:v0.2.0 --help

# Or set environment variable
export PORTL_IMAGE=ghcr.io/hebaghazali/portl:v0.2.0
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
```

## 🐛 Troubleshooting

### Docker Not Running

```bash
# Check Docker status
docker info

# Start Docker Desktop if needed
# Windows: Start from Start Menu
# macOS: Start from Applications
# Linux: sudo systemctl start docker
```

### Permission Issues

```bash
# Check file permissions
ls -la migration.yaml

# Fix permissions if needed
chmod 644 migration.yaml
```

### Network Issues

```bash
# Test network connectivity
docker run --rm ghcr.io/hebaghazali/portl:latest --version

# Check if image exists
docker images | grep portl
```

### Wrapper Issues

```bash
# Check wrapper installation
ls -la ~/.local/bin/portl

# Reinstall wrapper
rm ~/.local/bin/portl
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
```

## 📚 Next Steps

- **Read the full documentation:** [README.md](README.md)
- **Explore examples:** Check the `examples/` directory
- **Join the community:** [GitHub Discussions](https://github.com/hebaghazali/portl/discussions)
- **Report issues:** [GitHub Issues](https://github.com/hebaghazali/portl/issues)

## 🆘 Need Help?

- **Documentation:** [README.md](README.md)
- **Issues:** [GitHub Issues](https://github.com/hebaghazali/portl/issues)
- **Discussions:** [GitHub Discussions](https://github.com/hebaghazali/portl/discussions)

---

**Happy migrating! 🚀**

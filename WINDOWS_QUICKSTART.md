# Portl Windows Quick Start

Get up and running with Portl on Windows in under 2 minutes using Docker.

## 🚀 Quick Start

### Option 1: One-Line Install (Recommended)

**PowerShell:**
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
portl --help
```

**Git Bash (if you have Git for Windows):**
```bash
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
portl --help
```

### Option 2: Direct Docker Usage

**PowerShell:**
```powershell
# Run portl directly with Docker
docker run --rm ghcr.io/hebaghazali/portl:latest --help

# Create your first migration
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

**Command Prompt:**
```cmd
REM Run portl directly with Docker
docker run --rm ghcr.io/hebaghazali/portl:latest --help

REM Create your first migration
docker run --rm -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

## 📋 Prerequisites

- **Docker Desktop for Windows** installed and running
- **PowerShell** (comes with Windows 10/11) or **Git Bash**
- **Internet connection** for pulling images

### Install Docker Desktop

1. Download from [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/)
2. Run the installer
3. Start Docker Desktop from the Start Menu
4. Wait for Docker to start (you'll see the whale icon in the system tray)

## 🎯 Your First Migration

### 1. Start the Wizard

**PowerShell:**
```powershell
# Using wrapper (if installed)
portl init

# Or using Docker directly
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

**Command Prompt:**
```cmd
REM Using wrapper (if installed)
portl init

REM Or using Docker directly
docker run --rm -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

### 2. Follow the Interactive Prompts

The wizard will ask you:
- **Source type:** CSV, Postgres, MySQL, or Google Sheets
- **Destination type:** Where to send the data
- **Field mapping:** How to map columns
- **Conflict strategy:** What to do with duplicates
- **Batch size:** How many rows to process at once

### 3. Run Your Migration

**PowerShell:**
```powershell
# Using wrapper
portl run migration.yaml

# Or using Docker
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest run migration.yaml
```

**Command Prompt:**
```cmd
REM Using wrapper
portl run migration.yaml

REM Or using Docker
docker run --rm -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest run migration.yaml
```

## 🔧 Common Use Cases

### CSV to Database

**PowerShell:**
```powershell
# Create migration config
portl init

# Run migration
portl run jobs/csv_to_db.yaml
```

**Command Prompt:**
```cmd
REM Create migration config
portl init

REM Run migration
portl run jobs/csv_to_db.yaml
```

### Database to Database

**PowerShell:**
```powershell
# Create migration config
portl init

# Run migration with environment variables
docker run --rm `
  -v "${PWD}:/work" -w /work `
  -e PORTL_SOURCE_DB_HOST=source-host `
  -e PORTL_DEST_DB_HOST=dest-host `
  ghcr.io/hebaghazali/portl:latest run jobs/db_to_db.yaml
```

**Command Prompt:**
```cmd
REM Create migration config
portl init

REM Run migration with environment variables
docker run --rm -v "%CD%:/work" -w /work -e PORTL_SOURCE_DB_HOST=source-host -e PORTL_DEST_DB_HOST=dest-host ghcr.io/hebaghazali/portl:latest run jobs/db_to_db.yaml
```

### Google Sheets to Database

**PowerShell:**
```powershell
# Set up API credentials
$env:PORTL_GOOGLE_CREDENTIALS_FILE="C:\path\to\credentials.json"

# Create migration config
portl init

# Run migration
portl run jobs/sheets_to_db.yaml
```

**Command Prompt:**
```cmd
REM Set up API credentials
set PORTL_GOOGLE_CREDENTIALS_FILE=C:\path\to\credentials.json

REM Create migration config
portl init

REM Run migration
portl run jobs/sheets_to_db.yaml
```

## 🐳 Docker-Specific Features

### Volume Mounting

Mount your current directory to access files:

**PowerShell:**
```powershell
docker run --rm -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

**Command Prompt:**
```cmd
docker run --rm -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest init
```

### Environment Variables

Pass configuration via environment variables:

**PowerShell:**
```powershell
docker run --rm `
  -e PORTL_API_KEY=your_key `
  -e PORTL_DB_PASSWORD=secret `
  ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

**Command Prompt:**
```cmd
docker run --rm -e PORTL_API_KEY=your_key -e PORTL_DB_PASSWORD=secret ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

### Environment Files

Use `.env` files for configuration:

**PowerShell:**
```powershell
# Create .env file
"PORTL_API_KEY=your_key" | Out-File -FilePath .env -Encoding ASCII
"PORTL_DB_HOST=localhost" | Add-Content -Path .env

# Use with Docker
docker run --rm --env-file .env -v "${PWD}:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

**Command Prompt:**
```cmd
REM Create .env file
echo PORTL_API_KEY=your_key > .env
echo PORTL_DB_HOST=localhost >> .env

REM Use with Docker
docker run --rm --env-file .env -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/migration.yaml
```

### Network Access

Access host services (useful for local databases):

**PowerShell:**
```powershell
docker run --rm `
  --add-host host.docker.internal:host-gateway `
  -v "${PWD}:/work" -w /work `
  ghcr.io/hebaghazali/portl:latest run jobs/local_db.yaml
```

**Command Prompt:**
```cmd
docker run --rm --add-host host.docker.internal:host-gateway -v "%CD%:/work" -w /work ghcr.io/hebaghazali/portl:latest run jobs/local_db.yaml
```

## 🔄 Updating Portl

### Update Wrapper

**PowerShell:**
```powershell
# Re-run the install script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
```

**Git Bash:**
```bash
# Re-run the install script
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
```

### Update Docker Image

**PowerShell/Command Prompt:**
```powershell
# Pull latest image
docker pull ghcr.io/hebaghazali/portl:latest

# Or pull specific version
docker pull ghcr.io/hebaghazali/portl:v0.2.0
```

## 🏷️ Version Pinning

For production use, pin to specific versions:

**PowerShell:**
```powershell
# Use specific version
docker run --rm ghcr.io/hebaghazali/portl:v0.2.0 --help

# Or set environment variable for wrapper
$env:PORTL_IMAGE="ghcr.io/hebaghazali/portl:v0.2.0"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
```

**Command Prompt:**
```cmd
REM Use specific version
docker run --rm ghcr.io/hebaghazali/portl:v0.2.0 --help

REM Or set environment variable for wrapper
set PORTL_IMAGE=ghcr.io/hebaghazali/portl:v0.2.0
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
```

## 🐛 Troubleshooting

### Docker Not Running

**Check Docker status:**
```powershell
docker info
```

**Start Docker Desktop:**
- Click the Docker Desktop icon in the system tray
- Or start from Start Menu → Docker Desktop

### Permission Issues

**Check file permissions:**
```powershell
Get-ChildItem migration.yaml | Select-Object Name, Attributes
```

**Fix permissions if needed:**
```powershell
# Unblock downloaded files
Unblock-File -Path "migration.yaml"
```

### Network Issues

**Test network connectivity:**
```powershell
docker run --rm ghcr.io/hebaghazali/portl:latest --version
```

**Check if image exists:**
```powershell
docker images | Select-String "portl"
```

### Wrapper Issues

**Check wrapper installation:**
```powershell
Test-Path "$env:USERPROFILE\.local\bin\portl.bat"
```

**Reinstall wrapper:**
```powershell
Remove-Item "$env:USERPROFILE\.local\bin\portl.bat" -ErrorAction SilentlyContinue
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.ps1" | Invoke-Expression
```

### PowerShell Execution Policy

If you get execution policy errors:

```powershell
# Check current policy
Get-ExecutionPolicy

# Set policy for current user (temporary)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or run the script directly
PowerShell -ExecutionPolicy Bypass -File install-portl.ps1
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

**Happy migrating on Windows! 🚀**

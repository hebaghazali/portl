# Docker Distribution Verification Checklist

This document provides step-by-step verification instructions for the Portl Docker distribution setup.

## Prerequisites

- Docker Desktop installed and running
- Git repository with the new files committed
- GitHub repository with Actions enabled

## Local Verification

### 1. Docker Build Test

```bash
# Build the image locally
docker build -t local/portl:test .

# Test basic functionality
docker run --rm local/portl:test --help
docker run --rm local/portl:test --version
docker run --rm local/portl:test init --help
docker run --rm local/portl:test run --help
```

**Expected Results:**
- Image builds successfully without errors
- All commands show help text and exit with code 0
- No permission errors (runs as non-root user)

### 2. Volume Mounting Test

```bash
# Create test directory
mkdir test-workdir
echo "test data" > test-workdir/test.txt

# Test volume mounting
docker run --rm -v "$(pWD):/work" -w /work local/portl:test --help

# Cleanup
rm -rf test-workdir
```

**Expected Results:**
- Volume mounting works correctly
- No permission errors accessing mounted files

### 3. Install Script Test

```bash
# Test install script syntax
bash -n scripts/install-portl.sh

# Test wrapper creation (dry run)
export PORTL_IMAGE="local/portl:test"
export HOME="/tmp/test-home"
mkdir -p "$HOME/.local/bin"
bash scripts/install-portl.sh
```

**Expected Results:**
- Install script has no syntax errors
- Wrapper script is created and executable
- Wrapper contains proper Docker run command

## CI/CD Verification

### 1. Push to GitHub

```bash
# Commit all changes
git add .
git commit -m "Add Docker distribution setup"
git push origin main
```

### 2. Check GitHub Actions

1. Go to your GitHub repository
2. Click on "Actions" tab
3. Verify the "Build and Push Docker Images" workflow runs
4. Check that it builds for both `linux/amd64` and `linux/arm64`

### 3. Verify Image Tags

After successful CI run, check that these tags exist in GHCR:
- `ghcr.io/hebaghazali/portl:latest`
- `ghcr.io/hebaghazali/portl:main` (or current commit SHA)

## Production Verification

### 1. Test Published Image

```bash
# Pull and test the published image
docker pull ghcr.io/hebaghazali/portl:latest
docker run --rm ghcr.io/hebaghazali/portl:latest --help
```

### 2. Test Install Script

```bash
# Test the install script from GitHub
curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash
portl --help
```

### 3. Test Release Tag

```bash
# Create and push a release tag
git tag v0.2.0
git push origin v0.2.0

# Verify the tagged image
docker pull ghcr.io/hebaghazali/portl:v0.2.0
docker run --rm ghcr.io/hebaghazali/portl:v0.2.0 --version
```

## Multi-Platform Testing

### 1. Test on Different Architectures

If you have access to different machines:

**Linux AMD64:**
```bash
docker run --rm --platform linux/amd64 ghcr.io/hebaghazali/portl:latest --help
```

**Linux ARM64 (Apple Silicon):**
```bash
docker run --rm --platform linux/arm64 ghcr.io/hebaghazali/portl:latest --help
```

### 2. Test on Different Operating Systems

- **Windows:** Test with Docker Desktop
- **macOS Intel:** Test with Docker Desktop
- **macOS Apple Silicon:** Test with Docker Desktop
- **Linux:** Test with Docker Engine

## Troubleshooting

### Common Issues

1. **Docker not running:**
   - Start Docker Desktop
   - Check `docker info` command

2. **Permission denied:**
   - Ensure Docker daemon is running
   - Check user is in docker group (Linux)

3. **Image not found:**
   - Verify image was built successfully
   - Check GHCR permissions
   - Ensure correct image name/tag

4. **Install script fails:**
   - Check Docker is running
   - Verify internet connection
   - Check script permissions

### Debug Commands

```bash
# Check Docker status
docker info

# List local images
docker images | grep portl

# Check image layers
docker history local/portl:test

# Inspect image
docker inspect local/portl:test

# Run with debug output
docker run --rm -it local/portl:test /bin/bash
```

## Success Criteria

✅ **Local Build:** Image builds without errors  
✅ **Basic Functionality:** All CLI commands work  
✅ **Volume Mounting:** File access works correctly  
✅ **Install Script:** Wrapper installs and works  
✅ **CI/CD:** GitHub Actions builds multi-arch images  
✅ **Published Image:** Image is available on GHCR  
✅ **Multi-Platform:** Works on different architectures  
✅ **Documentation:** README has clear usage instructions  

## Next Steps

After successful verification:

1. **Create first release:** `git tag v0.2.0 && git push origin v0.2.0`
2. **Update documentation:** Add any missing usage examples
3. **Monitor usage:** Check GHCR download statistics
4. **Gather feedback:** Ask users to test the Docker distribution
5. **Iterate:** Improve based on user feedback

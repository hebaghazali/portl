#!/bin/bash

# Test script for Docker build and functionality
set -e

echo "🐳 Testing Portl Docker Build"
echo "=============================="

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    echo "   On Windows: Start Docker Desktop from Start Menu"
    echo "   On macOS: Start Docker Desktop from Applications"
    echo "   On Linux: sudo systemctl start docker"
    exit 1
fi

echo "✅ Docker is running"

# Build the image
echo "🔨 Building Docker image..."
docker build -t local/portl:test .

echo "✅ Docker image built successfully"

# Test basic functionality
echo "🧪 Testing basic functionality..."

echo "  Testing --help..."
if docker run --rm local/portl:test --help &> /dev/null; then
    echo "  ✅ --help works"
else
    echo "  ❌ --help failed"
    exit 1
fi

echo "  Testing --version..."
if docker run --rm local/portl:test --version &> /dev/null; then
    echo "  ✅ --version works"
else
    echo "  ❌ --version failed"
    exit 1
fi

echo "  Testing init command..."
if docker run --rm local/portl:test init --help &> /dev/null; then
    echo "  ✅ init --help works"
else
    echo "  ❌ init --help failed"
    exit 1
fi

echo "  Testing run command..."
if docker run --rm local/portl:test run --help &> /dev/null; then
    echo "  ✅ run --help works"
else
    echo "  ❌ run --help failed"
    exit 1
fi

# Test with volume mounting
echo "  Testing volume mounting..."
mkdir -p test-workdir
echo "test data" > test-workdir/test.txt

if docker run --rm -v "$(pwd)/test-workdir:/work" -w /work local/portl:test --help &> /dev/null; then
    echo "  ✅ Volume mounting works"
else
    echo "  ❌ Volume mounting failed"
    exit 1
fi

# Cleanup
rm -rf test-workdir

echo ""
echo "🎉 All tests passed! Docker image is working correctly."
echo ""
echo "Next steps:"
echo "1. Push to GitHub to trigger CI/CD"
echo "2. Test the install script: curl -fsSL https://raw.githubusercontent.com/hebaghazali/portl/main/scripts/install-portl.sh | bash"
echo "3. Create a release tag: git tag v0.2.0 && git push origin v0.2.0"

#!/bin/bash

# Test script for the install wrapper
set -e

echo "🔧 Testing Portl Install Wrapper"
echo "================================="

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Test the install script locally
echo "📦 Testing install script..."

# Create a temporary directory for testing
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

# Copy the install script
cp ../../scripts/install-portl.sh .

# Make it executable
chmod +x install-portl.sh

# Test the script (dry run)
echo "  Testing install script syntax..."
if bash -n install-portl.sh; then
    echo "  ✅ Install script syntax is valid"
else
    echo "  ❌ Install script has syntax errors"
    exit 1
fi

# Test the wrapper creation (without actually installing)
echo "  Testing wrapper creation..."
export PORTL_IMAGE="local/portl:test"
export HOME="$TEST_DIR"

# Create .local/bin directory
mkdir -p "$HOME/.local/bin"

# Run the install script
if ./install-portl.sh; then
    echo "  ✅ Install script runs successfully"
else
    echo "  ❌ Install script failed"
    exit 1
fi

# Check if wrapper was created
if [ -f "$HOME/.local/bin/portl" ]; then
    echo "  ✅ Wrapper script was created"
else
    echo "  ❌ Wrapper script was not created"
    exit 1
fi

# Check if wrapper is executable
if [ -x "$HOME/.local/bin/portl" ]; then
    echo "  ✅ Wrapper script is executable"
else
    echo "  ❌ Wrapper script is not executable"
    exit 1
fi

# Test wrapper content
echo "  Testing wrapper content..."
if grep -q "docker run" "$HOME/.local/bin/portl"; then
    echo "  ✅ Wrapper contains Docker run command"
else
    echo "  ❌ Wrapper missing Docker run command"
    exit 1
fi

if grep -q "PORTL_IMAGE" "$HOME/.local/bin/portl"; then
    echo "  ✅ Wrapper uses PORTL_IMAGE variable"
else
    echo "  ❌ Wrapper missing PORTL_IMAGE variable"
    exit 1
fi

# Cleanup
cd - > /dev/null
rm -rf "$TEST_DIR"

echo ""
echo "🎉 Install wrapper tests passed!"
echo ""
echo "The install script is ready for distribution."

#!/bin/bash

# Portl CLI Docker Wrapper Installer
# This script installs a lightweight wrapper that runs portl via Docker

set -e

# Configuration
REGISTRY_REPO="${PORTL_REGISTRY:-ghcr.io/hebaghazali/portl}"
DEFAULT_IMAGE="${REGISTRY_REPO}:latest"
IMAGE="${PORTL_IMAGE:-$DEFAULT_IMAGE}"
INSTALL_DIR="$HOME/.local/bin"
WRAPPER_PATH="$INSTALL_DIR/portl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed and running
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Create install directory if it doesn't exist
create_install_dir() {
    if [ ! -d "$INSTALL_DIR" ]; then
        log_info "Creating directory: $INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
    fi
}

# Create the wrapper script
create_wrapper() {
    log_info "Creating portl wrapper script..."
    
    cat > "$WRAPPER_PATH" << EOF
#!/bin/bash

# Portl CLI Docker Wrapper
# This script runs portl via Docker with proper volume mounting and environment handling

# Configuration
IMAGE="${IMAGE}"
WORK_DIR="\${PWD:-/tmp}"

# Check if we're in a TTY
if [ -t 0 ] && [ -t 1 ]; then
    TTY_FLAG="-it"
else
    TTY_FLAG=""
fi

# Build Docker run command
DOCKER_CMD="docker run --rm \${TTY_FLAG}"

# Mount current directory as work directory
DOCKER_CMD="\${DOCKER_CMD} -v \"\${WORK_DIR}:/work\" -w /work"

# Pass through PORTL_* environment variables
for var in \$(env | grep '^PORTL_' | cut -d= -f1); do
    DOCKER_CMD="\${DOCKER_CMD} -e \${var}"
done

# Add host networking for localhost access (useful for local databases)
if [[ "\$OSTYPE" == "linux-gnu"* ]]; then
    DOCKER_CMD="\${DOCKER_CMD} --add-host host.docker.internal:host-gateway"
fi

# Execute the command
exec \${DOCKER_CMD} \${IMAGE} "\$@"
EOF

    chmod +x "$WRAPPER_PATH"
}

# Test the installation
test_installation() {
    log_info "Testing installation..."
    
    if "$WRAPPER_PATH" --version &> /dev/null; then
        log_success "Installation test passed!"
    else
        log_warning "Installation test failed, but wrapper was created."
        log_info "You may need to pull the Docker image manually:"
        log_info "  docker pull $IMAGE"
    fi
}

# Check PATH configuration
check_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        log_warning "~/.local/bin is not in your PATH."
        log_info "Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo ""
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        log_info "Then restart your shell or run: source ~/.bashrc"
    else
        log_success "~/.local/bin is already in your PATH."
    fi
}

# Main installation process
main() {
    log_info "Installing Portl CLI Docker wrapper..."
    log_info "Image: $IMAGE"
    
    check_docker
    create_install_dir
    create_wrapper
    test_installation
    check_path
    
    log_success "Portl CLI wrapper installed successfully!"
    log_info "You can now run: portl --help"
    log_info "To update the image, run: docker pull $IMAGE"
}

# Run main function
main "$@"

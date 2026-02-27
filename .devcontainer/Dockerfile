FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# Base tooling
RUN apt-get update -o Acquire::Retries=3 \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    build-essential \
    unzip \
 && rm -rf /var/lib/apt/lists/*

# Install DuckDB CLI (arch-aware)
ARG DUCKDB_VERSION=1.1.3
RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in \
      x86_64) duck_arch="linux-amd64" ;; \
      aarch64|arm64) duck_arch="linux-aarch64" ;; \
      *) echo "Unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/duckdb.zip \
      "https://github.com/duckdb/duckdb/releases/download/v${DUCKDB_VERSION}/duckdb_cli-${duck_arch}.zip"; \
    unzip /tmp/duckdb.zip -d /usr/local/bin; \
    rm -f /tmp/duckdb.zip; \
    chmod +x /usr/local/bin/duckdb; \
    duckdb --version

# Install uv for the vscode user
USER vscode
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/vscode/.local/bin:${PATH}"

# Install Homebrew (Linux) and Astro CLI
# Note: brew shellenv needs to be made persistent via ENV (not eval in a RUN).
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
 && /home/linuxbrew/.linuxbrew/bin/brew install astro

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:/home/vscode/.local/bin:${PATH}"

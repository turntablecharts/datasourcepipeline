#!/usr/bin/env bash
set -euo pipefail

# Run in the deployed application directory, including Oryx-extracted builds.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v gpg >/dev/null 2>&1; then
    if ! command -v apt-get >/dev/null 2>&1 || [ "$(id -u)" -ne 0 ]; then
        echo "GnuPG is missing; automatic installation requires apt-get and root access." >&2
        exit 1
    fi
    echo "Installing GnuPG for Audiomack decryption..."
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gnupg ca-certificates
fi

export GPG_BINARY="$(command -v gpg)"
"$GPG_BINARY" --version

# A single worker owns the in-process ingestion scheduler.
exec python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1

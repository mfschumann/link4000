#!/usr/bin/env bash

set -euo pipefail  # optional: stop on command failure, remove if you want to keep going after errors

LOGFILE="setup.log"
PREFIX=".env"

{
    echo "[$(date)] Installing bzip2"
    apt-get update && apt-get install -y bzip2

    echo "[$(date)] Installing micromamba"
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba

    echo "[$(date)] Setting up environment at ./${PREFIX}"
    ./bin/micromamba create -y -p ./${PREFIX} -f conda-forge-lock.yml

    echo "[$(date)] Setup completed (exit code ignored)"
} 2>&1 | tee "$LOGFILE"

# Override any exit code and exit with 0
exit 0

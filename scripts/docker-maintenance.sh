#!/usr/bin/env bash
# Reclaim Docker disk after rebuilds. Docker never prunes on its own, so repeated
# `compose up --build` piles up dangling image layers and build cache, and the WSL
# vhdx grows but never shrinks. This prunes safely and shows how to compact the vhdx.
#
# SAFE BY DEFAULT: never prunes volumes, so your database (pgdata) is untouched.
#   ./scripts/docker-maintenance.sh          # dangling images + build cache + stopped containers
#   ./scripts/docker-maintenance.sh --deep   # also remove unused (tagged) images
set -euo pipefail

echo "=== Docker disk usage before ==="
docker system df

echo
echo "=== Pruning (volumes are NEVER touched — your data is safe) ==="
if [ "${1:-}" = "--deep" ]; then
  # -a also removes unused tagged images (they re-pull/rebuild on next up).
  docker system prune -af
else
  # Removes stopped containers, dangling images, unused networks, and build cache.
  docker system prune -f
fi

echo
echo "=== Docker disk usage after ==="
docker system df

cat <<'NOTE'

--- To also SHRINK the WSL disk file (it grows but never shrinks on its own) ---
The pruned space is freed inside the vhdx but the file stays large on disk. To
reclaim it on the host, from a Windows PowerShell (Docker can stay running):

  wsl --shutdown
  # then, elevated (Hyper-V tools) OR use Docker Desktop > Settings >
  # Resources > "Clean / Purge data" for the build cache, and restart Docker.

Simplest routine: run this script after a batch of rebuilds, and prefer building
once over repeatedly. Fast-screen analyses (skip_llm) don't add image churn.
NOTE

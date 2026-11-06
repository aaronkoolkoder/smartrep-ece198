#!/bin/zsh
cd "$(dirname "$0")/bridge" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "Set up bridge/.venv using the README first."
  exit 1
fi
# Hardware uses its own database: simulation references must not count real reps.
exec .venv/bin/python -m smartrep --db smartrep-hardware.db

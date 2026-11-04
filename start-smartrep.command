#!/bin/zsh
# Relaunch the installed local simulation from Finder or Terminal.
cd "$(dirname "$0")/bridge" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "Set up bridge/.venv using the README first."
  exit 1
fi
exec .venv/bin/python -m smartrep --simulate --crowd --db smartrep-demo.db

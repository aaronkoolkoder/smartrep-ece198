#!/bin/zsh
cd "$(dirname "$0")/bridge" || exit 1
exec .venv/bin/python -m smartrep --small-movement-demo --db smartrep-small-demo.db

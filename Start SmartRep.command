#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x bridge/.venv/bin/python ]]; then
  echo "Missing Python environment. Follow the setup steps in README.md."
  read "?Press Enter to close."
  exit 1
fi
bridge/.venv/bin/python tools/launch_phone.py
read "?Press Enter to close."

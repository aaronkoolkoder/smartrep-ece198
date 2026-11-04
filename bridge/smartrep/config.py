"""Load tuning values from the same TOML file for tools and the bridge."""
from pathlib import Path
import tomllib


def load_config(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "config.toml"
    return tomllib.loads(path.read_text())

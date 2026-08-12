from pathlib import Path

from xdg import XDG_DATA_HOME

DATA_DIR = Path(XDG_DATA_HOME) / "st3"
DATA_DIR.mkdir(parents=True, exist_ok=True)

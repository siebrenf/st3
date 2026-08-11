from pathlib import Path

from xdg import XDG_DATA_HOME

data_dir = Path(XDG_DATA_HOME) / "st3"
data_dir.mkdir(parents=True, exist_ok=True)

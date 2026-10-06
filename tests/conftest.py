"""把插件仓库父目录与宿主 src 加入 sys.path。"""

import sys
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parents[2]


def _find_host_src() -> Path:
    for base in (PARENT_DIR.parent, PARENT_DIR):
        candidate = base / "SakuraMediaBE" / "src"
        if candidate.is_dir():
            return candidate
    return PARENT_DIR.parent / "SakuraMediaBE" / "src"


for path in (PARENT_DIR, _find_host_src()):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

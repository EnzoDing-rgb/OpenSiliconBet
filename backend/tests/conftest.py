"""保证 `pytest backend/tests` 从仓库根运行时能 import `baton` 等模块。"""

import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent
_root = _backend.parent
for p in (_root, _backend):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

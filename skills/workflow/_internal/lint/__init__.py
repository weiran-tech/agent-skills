# ============================================================
# 一致性检查包（lint）—— 拆自原 _internal/doc_lint.py
# 入口：python3 -m _internal.lint（见 __main__.py）；setup.sh 一键跑
# 职责（单一）：
#   vocab.py      手写 md 词表与 model 一致性（原 doc_lint 扫描部分）
#   model_meta.py model/ 文件结构元数据校验（原 _check_model_meta）
# 共用：ROOT（skill 根）、_MODEL_DIR（model/）
# ============================================================
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # _internal/lint/ → skill 根
_MODEL_DIR = ROOT / "model"

if str(ROOT) not in sys.path:   # 使 engine 可导入（任意 cwd 兜底）
    sys.path.insert(0, str(ROOT))

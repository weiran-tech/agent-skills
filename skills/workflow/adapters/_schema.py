# ============================================================
# 轻量 JSON Schema 子集校验器 — 只支持 model 中 schema 用到的结构
# 保证 events.schema.json / config.schema.json 是唯一契约源，不在 Python 里复制字段定义
# 支持：type / required / properties / enum / const / minimum / maximum /
#        additionalProperties:false / items / 本地 $ref(#/definitions/...)
# ============================================================
from __future__ import annotations

import json
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
_EVENTS_SCHEMA_PATH = MODEL_DIR / "events.schema.json"
_CONFIG_SCHEMA_PATH = MODEL_DIR / "config.schema.json"

_schema_cache: dict[str, dict] = {}


class SchemaError(ValueError):
    pass


def _load(path: Path) -> dict:
    key = str(path)
    if key not in _schema_cache:
        with open(path) as fh:
            _schema_cache[key] = json.load(fh)
    return _schema_cache[key]


def _resolve(node, schema: dict) -> dict:
    if isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/definitions/"):
            return schema["definitions"][ref.split("/")[-1]]
        raise SchemaError(f"不支持的 $ref: {ref}")
    return node


def _validate(node, value, path: str, schema: dict) -> None:
    node = _resolve(node, schema)
    if not isinstance(node, dict):
        raise SchemaError(f"schema 节点非法: {path}")
    if "const" in node:
        if value != node["const"]:
            raise SchemaError(f"{path}: 期望 {node['const']!r}，实际 {value!r}")
        return
    if "enum" in node:
        if value not in node["enum"]:
            raise SchemaError(f"{path}: 值 {value!r} 不在允许集合 {node['enum']}")
        return
    t = node.get("type")
    if t == "object":
        if not isinstance(value, dict):
            raise SchemaError(f"{path}: 期望 object，实际 {type(value).__name__}")
        for req in node.get("required", []):
            if req not in value:
                raise SchemaError(f"{path}: 缺必填字段 {req!r}")
        props = node.get("properties", {})
        for k, v in value.items():
            if k not in props:
                if node.get("additionalProperties") is False:
                    raise SchemaError(f"{path}: 未知字段 {k!r}")
                continue
            _validate(props[k], v, f"{path}.{k}", schema)
    elif t == "array":
        if not isinstance(value, list):
            raise SchemaError(f"{path}: 期望 array")
        items = node.get("items")
        if items:
            for i, it in enumerate(value):
                _validate(items, it, f"{path}[{i}]", schema)
    elif t == "string":
        if not isinstance(value, str):
            raise SchemaError(f"{path}: 期望 string，实际 {type(value).__name__}")
    elif t in ("integer", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaError(f"{path}: 期望 {t}")
        if "minimum" in node and value < node["minimum"]:
            raise SchemaError(f"{path}: 小于 minimum {node['minimum']}")
        if "maximum" in node and value > node["maximum"]:
            raise SchemaError(f"{path}: 大于 maximum {node['maximum']}")
    elif t == "boolean":
        if not isinstance(value, bool):
            raise SchemaError(f"{path}: 期望 boolean")


def validate_event_payload(event: str, payload: dict) -> None:
    schema = _load(_EVENTS_SCHEMA_PATH)
    node = schema["properties"].get(event)
    if node is None:
        raise SchemaError(f"未知事件: {event}")
    _validate(node, payload, event, schema)


def validate_config(cfg: dict) -> None:
    schema = _load(_CONFIG_SCHEMA_PATH)
    _validate(schema, cfg, "config", schema)

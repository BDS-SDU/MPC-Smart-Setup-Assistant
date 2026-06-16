"""Utility helpers for config merging and formatting."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def to_pretty_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, indent=2)


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def deep_merge_existing(existing: Any, incoming: Any) -> Any:
    """Merge incoming data over existing data while keeping old non-empty values."""

    if isinstance(existing, BaseModel):
        existing = existing.model_dump(mode="json")
    if isinstance(incoming, BaseModel):
        incoming = incoming.model_dump(mode="json")

    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged: dict[str, Any] = dict(existing)
        for key, new_value in incoming.items():
            old_value = merged.get(key)
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                merged[key] = deep_merge_existing(old_value, new_value)
            elif is_empty(new_value) and not is_empty(old_value):
                merged[key] = old_value
            else:
                merged[key] = new_value
        return merged

    if is_empty(incoming) and not is_empty(existing):
        return existing
    return incoming


def merge_models(existing: ModelT, incoming: ModelT, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate(deep_merge_existing(existing, incoming))

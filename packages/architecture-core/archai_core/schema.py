from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OP_TYPES = {"input", "output", "conv3x3", "conv1x1", "skip", "avg_pool3x3", "none"}
ACTIVATIONS = {"relu", "gelu", "none"}
NORMS = {"batch", "layer", "none"}


class TensorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    channels: int = Field(gt=0, le=4096)
    height: int = Field(gt=0, le=4096)
    width: int = Field(gt=0, le=4096)


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    op: str
    channels: int = Field(gt=0, le=4096)
    kernel_size: int = Field(default=3, ge=1, le=7)
    normalization: str = "batch"
    activation: str = "relu"

    @field_validator("op")
    @classmethod
    def op_allowed(cls, value: str) -> str:
        if value not in OP_TYPES:
            raise ValueError(f"unsupported operation: {value}")
        return value

    @field_validator("normalization")
    @classmethod
    def norm_allowed(cls, value: str) -> str:
        if value not in NORMS:
            raise ValueError(f"unsupported normalization: {value}")
        return value

    @field_validator("activation")
    @classmethod
    def activation_allowed(cls, value: str) -> str:
        if value not in ACTIVATIONS:
            raise ValueError(f"unsupported activation: {value}")
        return value


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str
    target: str


class Architecture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    architecture_id: str | None = None
    schema_version: Literal["1.0"] = "1.0"
    nodes: list[Node] = Field(min_length=2, max_length=64)
    edges: list[Edge] = Field(min_length=1, max_length=256)
    input_spec: TensorSpec
    output_classes: int = Field(gt=1, le=10000)
    search_space: str = "nasbench201"
    generator_version: str = "manual"
    seed: int | None = None
    lineage: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    def canonical_dict(self) -> dict:
        data = self.model_dump(exclude={"architecture_id"}, mode="json")
        data["nodes"] = sorted(data["nodes"], key=lambda x: x["id"])
        data["edges"] = sorted(data["edges"], key=lambda x: (x["source"], x["target"]))
        return data

    def canonical_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()[:24]

    def with_id(self) -> Architecture:
        if self.architecture_id == self.content_hash():
            return self
        return self.model_copy(update={"architecture_id": self.content_hash()})

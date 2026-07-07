"""Shared schema base classes and generic containers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for response models read from ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """A simple offset-paginated result envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str

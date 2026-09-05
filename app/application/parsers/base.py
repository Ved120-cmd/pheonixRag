from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class ParserStrategy(ABC):
    @abstractmethod
    def parse(self, data: bytes, filename: str, mime_type: str) -> dict:
        """Parse raw file bytes and return a dict with keys:
        - text: string
        - pages: int | None
        - char_count: int
        - word_count: int
        - structured: optional structured result (dict)
        """


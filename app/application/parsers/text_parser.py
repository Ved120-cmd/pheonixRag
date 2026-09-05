from __future__ import annotations

from .base import ParserStrategy


class TextParser(ParserStrategy):
    def parse(self, data: bytes, filename: str, mime_type: str) -> dict:
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("utf-8", errors="ignore")

        words = len(text.split())
        chars = len(text)
        return {
            "text": text,
            "pages": 1,
            "char_count": chars,
            "word_count": words,
            "structured": {"text": text},
        }

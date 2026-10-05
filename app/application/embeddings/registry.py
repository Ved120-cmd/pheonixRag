from __future__ import annotations

from collections.abc import Callable

from app.application.interfaces.embedding_provider import EmbeddingProvider
from app.domain.entities.embedding import EmbeddingConfig


ProviderFactory = Callable[[EmbeddingConfig], EmbeddingProvider]


class EmbeddingProviderRegistry:
    def __init__(self, factory: ProviderFactory) -> None:
        self._factory = factory
        self._providers: dict[str, EmbeddingProvider] = {}

    def get(self, config: EmbeddingConfig) -> EmbeddingProvider:
        provider = self._providers.get(config.fingerprint)
        if provider is None:
            provider = self._factory(config)
            self._providers[config.fingerprint] = provider
        return provider

    def invalidate(self, fingerprint: str | None = None) -> None:
        keys = [fingerprint] if fingerprint else list(self._providers)
        for key in keys:
            provider = self._providers.pop(key, None)
            if provider is not None:
                provider.close()

    def close(self) -> None:
        self.invalidate()
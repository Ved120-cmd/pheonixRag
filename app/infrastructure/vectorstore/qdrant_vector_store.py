from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from app.domain.entities.indexing import VectorCollectionConfig, VectorPoint, VectorSearchHit


class QdrantVectorStore:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client
        self._tenant_sharding: dict[str, bool] = {}
        self._collection_dimensions: dict[str, int] = {}

    async def ensure_collection(self, config: VectorCollectionConfig) -> str:
        collection = config.collection_name
        if not await self._client.collection_exists(collection):
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(
                    size=config.dimension,
                    distance=self._distance(config.distance),
                    on_disk=True,
                ),
                on_disk_payload=True,
                sharding_method=(models.ShardingMethod.CUSTOM if config.tenant_sharding else None),
                metadata={
                    "model_name": config.model_name,
                    "model_version": config.model_version,
                    "embedding_fingerprint": config.embedding_fingerprint,
                    "dimension": config.dimension,
                    "distance": config.distance,
                    "tenant_sharding": config.tenant_sharding,
                },
            )
        await self._verify_collection(collection, config)
        info = await self._client.get_collection(collection)
        indexed_fields = set((info.payload_schema or {}).keys())
        await self._create_payload_indexes(collection, indexed_fields)
        self._tenant_sharding[collection] = config.tenant_sharding
        self._collection_dimensions[collection] = config.dimension
        return collection

    async def _create_payload_indexes(self, collection_name: str, existing: set[str]) -> None:
        indexes = {
            "tenant_id": models.PayloadSchemaType.KEYWORD,
            "document_id": models.PayloadSchemaType.KEYWORD,
            "document_version": models.PayloadSchemaType.INTEGER,
            "chunk_set_fingerprint": models.PayloadSchemaType.KEYWORD,
            "chunk_id": models.PayloadSchemaType.KEYWORD,
            "page_numbers": models.PayloadSchemaType.INTEGER,
            "document_type": models.PayloadSchemaType.KEYWORD,
            "tags": models.PayloadSchemaType.KEYWORD,
            "status": models.PayloadSchemaType.KEYWORD,
            "created_at": models.PayloadSchemaType.DATETIME,
        }
        for field_name, schema in indexes.items():
            if field_name in existing:
                continue
            await self._client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )

    async def _verify_collection(self, collection_name: str, config: VectorCollectionConfig) -> None:
        info = await self._client.get_collection(collection_name)
        vectors = info.config.params.vectors
        if isinstance(vectors, dict):
            if len(vectors) != 1 or "default" not in vectors:
                raise ValueError("collection has an incompatible named-vector configuration")
            vectors = vectors["default"]
        if vectors.size != config.dimension:
            raise ValueError(
                f"collection dimension mismatch: expected {config.dimension}, got {vectors.size}"
            )
        if vectors.distance != self._distance(config.distance):
            raise ValueError("collection distance metric does not match configured metric")
        metadata = info.config.metadata or {}
        expected = {
            "model_name": config.model_name,
            "model_version": config.model_version,
            "embedding_fingerprint": config.embedding_fingerprint,
            "dimension": config.dimension,
            "distance": config.distance,
            "tenant_sharding": config.tenant_sharding,
        }
        if not metadata or any(metadata.get(key) != value for key, value in expected.items()):
            raise ValueError("collection embedding metadata is incompatible with requested configuration")

    async def collection_info(self, collection_name: str) -> dict[str, object]:
        info = await self._client.get_collection(collection_name)
        return {
            "name": collection_name,
            "status": str(info.status),
            "points_count": info.points_count or 0,
            "vectors_count": info.indexed_vectors_count or 0,
            "optimizer_status": str(info.optimizer_status),
            "payload_schema": sorted((info.payload_schema or {}).keys()),
            "configuration": info.config.metadata or {},
        }

    async def upsert_batch(
        self, collection_name: str, tenant_id: UUID, points: Sequence[VectorPoint]
    ) -> int:
        if not points:
            return 0
        for point in points:
            if not point.vector or any(not math.isfinite(value) for value in point.vector):
                raise ValueError("vector must be non-empty and contain only finite values")
            expected_dimension = self._collection_dimensions.get(collection_name)
            if expected_dimension is None:
                info = await self._client.get_collection(collection_name)
                vectors = info.config.params.vectors
                if isinstance(vectors, dict):
                    vectors = vectors.get("default")
                expected_dimension = vectors.size if vectors else None
            if expected_dimension is not None and len(point.vector) != expected_dimension:
                raise ValueError(
                    f"vector dimension mismatch: expected {expected_dimension}, got {len(point.vector)}"
                )
            if str(point.payload.get("tenant_id")) != str(tenant_id):
                raise ValueError("point tenant does not match shard tenant")
        tenant_sharding = self._tenant_sharding.get(collection_name, True)
        if tenant_sharding:
            await self._ensure_tenant_shard(collection_name, tenant_id)
        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(id=str(point.id), vector=list(point.vector), payload=point.payload)
                for point in points
            ],
            wait=True,
            shard_key_selector=str(tenant_id) if tenant_sharding else None,
        )
        return len(points)

    async def _ensure_tenant_shard(self, collection_name: str, tenant_id: UUID) -> None:
        if not hasattr(self._client, "create_shard_key"):
            return
        shard_key = str(tenant_id)
        shard_response = await self._client.list_shard_keys(collection_name)
        existing = {str(item.shard_key) for item in shard_response.shard_keys}
        if shard_key not in existing:
            try:
                await self._client.create_shard_key(collection_name, shard_key)
            except Exception:
                shard_response = await self._client.list_shard_keys(collection_name)
                if shard_key not in {str(item.shard_key) for item in shard_response.shard_keys}:
                    raise

    async def delete_document(
        self,
        collection_name: str,
        tenant_id: UUID,
        document_id: UUID,
        version: int | None = None,
        retain_chunk_set_fingerprint: str | None = None,
    ) -> int:
        tenant_sharding = self._tenant_sharding.get(collection_name, True)
        conditions = [
            self._match("tenant_id", str(tenant_id)),
            self._match("document_id", str(document_id)),
        ]
        if version is not None:
            conditions.append(self._match("document_version", version))
        filters = models.Filter(must=conditions)
        if retain_chunk_set_fingerprint is not None:
            filters.must_not = [self._match("chunk_set_fingerprint", retain_chunk_set_fingerprint)]
        result = await self._client.delete(
            collection_name,
            points_selector=models.FilterSelector(filter=filters),
            wait=True,
            shard_key_selector=str(tenant_id) if tenant_sharding else None,
        )
        return int(result.status == models.UpdateStatus.COMPLETED)

    async def search(
        self,
        collection_name: str,
        tenant_id: UUID,
        vector: Sequence[float],
        limit: int,
        active_document_versions: Mapping[UUID, tuple[int, str]],
        payload_filters: Mapping[str, str | int | Sequence[str] | Sequence[int]] | None = None,
    ) -> list[VectorSearchHit]:
        if not vector or any(not math.isfinite(value) for value in vector):
            raise ValueError("query vector must be non-empty and finite")
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not active_document_versions:
            return []
        allowed_filters = {
            "document_id",
            "document_version",
            "chunk_id",
            "page_numbers",
            "document_type",
            "tags",
            "status",
            "created_at",
        }
        filters = payload_filters or {}
        unknown = set(filters) - allowed_filters
        if unknown:
            raise ValueError(f"unsupported payload filter field: {sorted(unknown)[0]}")
        tenant_sharding = self._tenant_sharding.get(collection_name, True)
        conditions = [self._match("tenant_id", str(tenant_id))]
        active_versions = [
            models.Filter(
                must=[
                    self._match("document_id", str(document_id)),
                    self._match("document_version", version),
                    self._match("chunk_set_fingerprint", chunk_set_fingerprint),
                ]
            )
            for document_id, (version, chunk_set_fingerprint) in active_document_versions.items()
        ]
        conditions.extend(self._filter_condition(field, value) for field, value in filters.items())
        response = await self._client.query_points(
            collection_name=collection_name,
            query=list(vector),
            query_filter=models.Filter(must=conditions, should=active_versions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
            shard_key_selector=str(tenant_id) if tenant_sharding else None,
        )
        return [
            VectorSearchHit(id=UUID(str(point.id)), score=point.score, payload=point.payload or {})
            for point in response.points
        ]

    @classmethod
    def _filter_condition(
        cls, field: str, value: str | int | Sequence[str] | Sequence[int]
    ) -> models.FieldCondition:
        if isinstance(value, (list, tuple, set)):
            return models.FieldCondition(key=field, match=models.MatchAny(any=list(value)))
        return cls._match(field, value)

    async def delete_collection(self, collection_name: str) -> None:
        if await self._client.collection_exists(collection_name):
            await self._client.delete_collection(collection_name)

    async def delete_points(self, collection_name: str, point_ids: Sequence[UUID], tenant_id: UUID) -> int:
        if not point_ids:
            return 0
        tenant_sharding = self._tenant_sharding.get(collection_name, True)
        result = await self._client.delete(
            collection_name,
            points_selector=[str(point_id) for point_id in point_ids],
            wait=True,
            shard_key_selector=str(tenant_id) if tenant_sharding else None,
        )
        return len(point_ids) if result.status == models.UpdateStatus.COMPLETED else 0

    async def update_collection_config(
        self, collection_name: str, optimizers_config: models.OptimizersConfigDiff
    ) -> bool:
        return await self._client.update_collection(
            collection_name=collection_name,
            optimizers_config=optimizers_config,
        )

    @staticmethod
    def _match(key: str, value: str | int) -> models.FieldCondition:
        return models.FieldCondition(key=key, match=models.MatchValue(value=value))

    @staticmethod
    def _distance(distance: str) -> models.Distance:
        return {
            "cosine": models.Distance.COSINE,
            "dot": models.Distance.DOT,
            "euclid": models.Distance.EUCLID,
        }[distance]
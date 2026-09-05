from app.config.settings import get_settings
from app.infrastructure.storage.minio_client import check_minio_health
from app.infrastructure.database.session import check_database_health
from app.infrastructure.cache.redis_client import check_redis_health
from app.infrastructure.vectorstore.qdrant_client import check_qdrant_health
import asyncio

settings = get_settings()
print('minio_endpoint', settings.minio_endpoint)
print('minio_secure', settings.minio_secure)
print('database_url', settings.database_url)
print('redis_url', settings.redis_url)
print('qdrant_url', settings.qdrant_url)
print('minio_health', check_minio_health())

async def main():
    print('db_health', await check_database_health())
    print('redis_health', await check_redis_health())
    print('qdrant_health', await check_qdrant_health())

asyncio.run(main())

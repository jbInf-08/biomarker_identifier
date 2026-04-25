"""
Redis cache service for performance optimization.
"""
import json
import logging
from datetime import timedelta
from typing import Any, Optional, Union

import redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based cache service for performance optimization."""

    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache service initialized successfully")
        except RedisError as e:
            logger.error(f"Failed to initialize Redis cache: {str(e)}")
            self.redis_client = None

    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except RedisError:
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.is_available():
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to get cache key {key}: {str(e)}")
            return None

    def set(
        self, key: str, value: Any, expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with optional expiration."""
        if not self.is_available():
            return False

        try:
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.set(key, serialized_value, ex=expire)
        except (RedisError, TypeError) as e:
            logger.warning(f"Failed to set cache key {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.is_available():
            return False

        try:
            return bool(self.redis_client.delete(key))
        except RedisError as e:
            logger.warning(f"Failed to delete cache key {key}: {str(e)}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self.is_available():
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning(f"Failed to delete pattern {pattern}: {str(e)}")
            return 0

    def clear(self) -> bool:
        """Remove all keys in the current Redis logical DB (FLUSHDB)."""
        if not self.is_available():
            return False
        try:
            self.redis_client.flushdb()
            return True
        except RedisError as e:
            logger.warning(f"Failed to clear cache: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_available():
            return False

        try:
            return bool(self.redis_client.exists(key))
        except RedisError as e:
            logger.warning(f"Failed to check existence of key {key}: {str(e)}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment numeric value in cache."""
        if not self.is_available():
            return None

        try:
            return self.redis_client.incrby(key, amount)
        except RedisError as e:
            logger.warning(f"Failed to increment key {key}: {str(e)}")
            return None

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for key."""
        if not self.is_available():
            return False

        try:
            return bool(self.redis_client.expire(key, seconds))
        except RedisError as e:
            logger.warning(f"Failed to set expiration for key {key}: {str(e)}")
            return False

    def get_stats(self) -> dict:
        """Get Redis server statistics."""
        if not self.is_available():
            return {"status": "unavailable"}

        try:
            info = self.redis_client.info()
            return {
                "status": "available",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
            }
        except RedisError as e:
            logger.warning(f"Failed to get Redis stats: {str(e)}")
            return {"status": "error", "error": str(e)}

    def _calculate_hit_rate(self, info: dict) -> float:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


# Global cache service instance
cache_service = CacheService()


# Cache decorator
def cached(key_prefix: str, expire: int = 3600):
    """Decorator to cache function results."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Try to get from cache
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, expire=expire)
            logger.debug(f"Cached result for key: {cache_key}")
            return result

        return wrapper

    return decorator


# Cache key generators
class CacheKeys:
    """Cache key generators for different data types."""

    @staticmethod
    def biomarker_results(run_id: str) -> str:
        """Generate cache key for biomarker results."""
        return f"biomarker_results:{run_id}"

    @staticmethod
    def analysis_status(run_id: str) -> str:
        """Generate cache key for analysis status."""
        return f"analysis_status:{run_id}"

    @staticmethod
    def clinical_annotations(gene_symbol: str, database: str) -> str:
        """Generate cache key for clinical annotations."""
        return f"clinical_annotations:{database}:{gene_symbol}"

    @staticmethod
    def pathway_analysis(run_id: str) -> str:
        """Generate cache key for pathway analysis."""
        return f"pathway_analysis:{run_id}"

    @staticmethod
    def user_sessions(user_id: str) -> str:
        """Generate cache key for user sessions."""
        return f"user_sessions:{user_id}"

    @staticmethod
    def report_generation(run_id: str, format: str) -> str:
        """Generate cache key for report generation."""
        return f"report_generation:{run_id}:{format}"

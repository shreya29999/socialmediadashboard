import logging
import redis

from app.core.config import (
    REDIS_URL,
    REDIS_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
)

logger = logging.getLogger(__name__)

def get_redis_client() -> redis.Redis:
    """
    Create and return a Redis client using centralized configuration.
    """

    return redis.Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        decode_responses=True,
        health_check_interval=30,
    )

def check_redis_health() -> bool:
    """
    Check whether Redis is reachable.
    """

    client = get_redis_client()

    try:
        client.ping()
        logger.info("Redis connection check successful.")
        return True

    except redis.RedisError:
        logger.exception("Redis connection check failed.")
        return False

    finally:
        try:
            client.close()
        except Exception:
            logger.exception("Failed to close Redis client.")
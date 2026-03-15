"""Redis-based sliding window rate limiter."""

from redis.asyncio import Redis

from app.core.exceptions import RateLimitExceeded


class RateLimiter:
    """
    Rate limiter using Redis INCR + EXPIRE (fixed window).

    Keys follow pattern: ratelimit:{service}:{identifier}
    Example: ratelimit:sp_api:catalog, ratelimit:api:192.168.1.1
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check_rate(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """
        Check if a request is within the rate limit.

        Returns True if allowed, raises RateLimitExceeded if not.
        """
        redis_key = f"ratelimit:{key}"
        current = await self.redis.incr(redis_key)

        if current == 1:
            # First request in this window — set expiry
            await self.redis.expire(redis_key, window_seconds)

        if current > max_requests:
            ttl = await self.redis.ttl(redis_key)
            raise RateLimitExceeded(
                detail=f"Rate limit exceeded for {key}: {max_requests} requests per {window_seconds}s",
                retry_after=max(1, ttl),
            )

        return True

    async def get_remaining(self, key: str, max_requests: int) -> int:
        """Get how many requests remain in the current window."""
        redis_key = f"ratelimit:{key}"
        current = await self.redis.get(redis_key)
        if current is None:
            return max_requests
        return max(0, max_requests - int(current))

    async def reset(self, key: str) -> None:
        """Reset a rate limit key."""
        await self.redis.delete(f"ratelimit:{key}")

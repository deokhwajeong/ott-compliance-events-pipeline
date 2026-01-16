"""Redis caching layer for performance optimization"""

import logging
import json
from typing import Any, Optional, List, Dict
import redis
import os
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage caching with Redis for improved performance"""
    
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.default_ttl = 300  # 5 minutes default
        self.is_connected = False
        self.client = None
        
        self._connect()
    
    def _connect(self) -> None:
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.client.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Using in-memory fallback.")
            self.is_connected = False
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_connected or not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache GET error for {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """Set value in cache"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.error(f"Cache SET error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache DELETE error for {key}: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern (e.g., 'user:*') with optimized SCAN"""
        if not self.is_connected or not self.client:
            return 0
        
        try:
            # Use SCAN instead of KEYS for better performance with large datasets
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.error(f"Cache CLEAR_PATTERN error: {e}")
            return 0
    
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache efficiently (single round-trip)"""
        if not self.is_connected or not self.client or not keys:
            return {}
        
        try:
            values = self.client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    try:
                        result[key] = json.loads(value)
                    except:
                        result[key] = value
            return result
        except Exception as e:
            logger.error(f"Cache MGET error: {e}")
            return {}
    
    def mset(self, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple values in cache efficiently using pipeline"""
        if not self.is_connected or not self.client or not data:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            pipeline = self.client.pipeline()
            
            for key, value in data.items():
                pipeline.setex(key, ttl, json.dumps(value))
            
            pipeline.execute()
            return True
        except Exception as e:
            logger.error(f"Cache MSET error: {e}")
            return False
    
    def get_user_recent_events(
        self,
        user_id: str,
        db_query_func
    ) -> List[Dict]:
        """
        Get recent events for user with caching.
        Falls back to database if not cached.
        """
        cache_key = f"user:{user_id}:recent_events"
        
        # Try cache first (very fast, ~0.1ms)
        cached_events = self.get(cache_key)
        if cached_events is not None:
            logger.debug(f"Cache HIT for {cache_key}")
            return cached_events
        
        logger.debug(f"Cache MISS for {cache_key}, querying database")
        
        # Query database if not cached (~10ms)
        events = db_query_func(user_id)
        
        # Store in cache for 5 minutes
        self.set(cache_key, events, ttl=300)
        
        return events
    
    def get_user_risk_profile(
        self,
        user_id: str,
        db_query_func
    ) -> Dict:
        """Get cached user risk profile"""
        cache_key = f"user:{user_id}:risk_profile"
        
        cached_profile = self.get(cache_key)
        if cached_profile is not None:
            return cached_profile
        
        profile = db_query_func(user_id)
        self.set(cache_key, profile, ttl=600)  # 10 minutes
        
        return profile
    
    def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate all cached data for a user (after violation)"""
        try:
            self.clear_pattern(f"user:{user_id}:*")
            logger.info(f"Invalidated cache for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for {user_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected or not self.client:
            return {"status": "disconnected"}
        
        try:
            info = self.client.info()
            return {
                "status": "connected",
                "used_memory_mb": info.get("used_memory") / (1024 * 1024),
                "total_keys": self.client.dbsize(),
                "connected_clients": info.get("connected_clients"),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"status": "error"}


# In-memory fallback cache for when Redis is unavailable
class InMemoryCache:
    """Simple in-memory cache fallback"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.max_size = 10000
    
    def get(self, key: str) -> Optional[Any]:
        """Get from memory cache"""
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set in memory cache"""
        if len(self.cache) >= self.max_size:
            # Simple FIFO eviction
            first_key = next(iter(self.cache))
            del self.cache[first_key]
        
        self.cache[key] = value
        return True
    
    def delete(self, key: str) -> bool:
        """Delete from memory cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern"""
        import fnmatch
        keys_to_delete = [k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self.cache[key]
        return len(keys_to_delete)


# Initialize cache manager
cache_manager = CacheManager()

# Create fallback cache
fallback_cache = InMemoryCache()


def cached(ttl: int = 300):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


def async_cached(ttl: int = 300):
    """Decorator for caching async function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator

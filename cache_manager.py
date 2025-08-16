"""
Cache Manager
Simple TTL-based in-memory cache for the D&D assistant system
"""
import time
from typing import Any, Optional


class SimpleInlineCache:
    """Simple TTL-based in-memory cache for basic caching needs"""
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key: str, default_ttl_hours: float = 1.0) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self.cache:
            return None
        
        # Check if expired
        current_time = time.time()
        if key in self.timestamps:
            cache_time, ttl_seconds = self.timestamps[key]
            if current_time - cache_time > ttl_seconds:
                # Expired, remove from cache
                del self.cache[key]
                del self.timestamps[key]
                return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any, ttl_hours: float = 1.0):
        """Set value in cache with TTL"""
        self.cache[key] = value
        self.timestamps[key] = (time.time(), ttl_hours * 3600)  # Convert hours to seconds
    
    def delete(self, key: str):
        """Delete specific key from cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
    
    def clear(self):
        """Clear all cached items"""
        self.cache.clear()
        self.timestamps.clear()
    
    def cleanup_expired(self):
        """Remove all expired items from cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, (cache_time, ttl_seconds) in self.timestamps.items():
            if current_time - cache_time > ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self.cache:
                del self.cache[key]
            del self.timestamps[key]
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        # Clean up expired items first
        self.cleanup_expired()
        
        return {
            'total_items': len(self.cache),
            'memory_usage_estimate': sum(len(str(k)) + len(str(v)) for k, v in self.cache.items()),
            'oldest_item_age_seconds': self._get_oldest_item_age()
        }
    
    def _get_oldest_item_age(self) -> float:
        """Get age of oldest cached item in seconds"""
        if not self.timestamps:
            return 0.0
        
        current_time = time.time()
        oldest_time = min(cache_time for cache_time, _ in self.timestamps.values())
        return current_time - oldest_time
    
    def get_cache_info(self) -> dict:
        """Get detailed cache information"""
        self.cleanup_expired()
        
        # Analyze cache by TTL ranges
        ttl_ranges = {
            'short_term': 0,    # < 1 hour
            'medium_term': 0,   # 1-6 hours
            'long_term': 0      # > 6 hours
        }
        
        for _, ttl_seconds in self.timestamps.values():
            ttl_hours = ttl_seconds / 3600
            if ttl_hours < 1:
                ttl_ranges['short_term'] += 1
            elif ttl_hours < 6:
                ttl_ranges['medium_term'] += 1
            else:
                ttl_ranges['long_term'] += 1
        
        return {
            'stats': self.get_stats(),
            'ttl_distribution': ttl_ranges,
            'cache_keys': list(self.cache.keys())
        }

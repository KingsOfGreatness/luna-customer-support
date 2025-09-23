from collections import defaultdict
from datetime import datetime, timedelta
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class SimpleRateLimiter:
    """Simple in-memory rate limiter for API endpoints"""
    
    def __init__(self, max_requests: int = 100, window_minutes: int = 1):
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.max_requests = max_requests
        self.window = timedelta(minutes=window_minutes)
        
    def is_allowed(self, api_key: str) -> bool:
        """Check if request is allowed for this API key"""
        now = datetime.now()
        
        # Clean old requests outside the window
        self.requests[api_key] = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < self.window
        ]
        
        # Check if under limit
        if len(self.requests[api_key]) < self.max_requests:
            self.requests[api_key].append(now)
            return True
        
        logger.warning(f"Rate limit exceeded for API key: {api_key}")
        return False
    
    def get_remaining(self, api_key: str) -> int:
        """Get remaining requests for this API key"""
        now = datetime.now()
        
        # Clean old requests
        self.requests[api_key] = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < self.window
        ]
        
        return max(0, self.max_requests - len(self.requests[api_key]))
    
    def reset(self, api_key: str):
        """Reset rate limit for specific API key"""
        self.requests[api_key] = []
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        now = datetime.now()
        stats = {}
        
        for api_key, req_times in self.requests.items():
            # Count requests in current window
            active_requests = [
                req for req in req_times
                if now - req < self.window
            ]
            stats[api_key] = {
                "requests_in_window": len(active_requests),
                "remaining": self.max_requests - len(active_requests),
                "max_requests": self.max_requests,
                "window_minutes": self.window.seconds // 60
            }
        
        return stats

# Global rate limiter instance
rate_limiter = SimpleRateLimiter(max_requests=100, window_minutes=1)
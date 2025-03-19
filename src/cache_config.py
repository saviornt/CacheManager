import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class CacheConfig:
    # Cache settings
    cache_dir: str = os.getenv("CACHE_DIR", ".cache")
    cache_file: str = os.getenv("CACHE_FILE", "cache.db")
    cache_max_size: int = int(os.getenv("CACHE_MAX_SIZE", "5000"))
    cache_ttl: float = float(os.getenv("CACHE_TTL", "300.0"))
    
    # Redis settings
    use_redis: bool = os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_username: str = os.getenv("REDIS_USERNAME", "")
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    
    # Retry settings
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    retry_delay: int = int(os.getenv("RETRY_DELAY", "2"))
    
    @property
    def full_redis_url(self) -> str:
        """
        Constructs the full Redis URL based on the individual settings.
        """
        scheme, _, host = self.redis_url.partition("://")
        host = host.split(":")[0]  # remove port if any exists
        
        credentials = ""
        if self.redis_username and self.redis_password:
            credentials = f"{self.redis_username}:{self.redis_password}@"
        elif self.redis_password:
            credentials = f":{self.redis_password}@"
            
        return f"{scheme}://{credentials}{host}:{self.redis_port}"

import asyncio
import logging
import random
from typing import Callable, Any, Optional, TypeVar, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class RetryOptions:
    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    should_retry: Optional[Callable[[Exception, int], bool]] = None

    def __post_init__(self):
        if self.should_retry is None:
            self.should_retry = lambda error, _: True


class ExponentialBackoff:
    def __init__(self, options: RetryOptions = None):
        self.options = options or RetryOptions()
        
    async def execute(
        self, 
        operation: Callable[[], Awaitable[T]], 
        operation_name: str = "operation"
    ) -> T:
        last_error = None
        
        for attempt in range(self.options.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(
                        f"Retrying {operation_name} (attempt {attempt + 1}/"
                        f"{self.options.max_retries + 1})"
                    )
                
                return await operation()
                
            except Exception as error:
                last_error = error
                
                if attempt == self.options.max_retries:
                    logger.error(
                        f"{operation_name} failed after {self.options.max_retries + 1} "
                        f"attempts: {error}"
                    )
                    raise error
                
                if not self.options.should_retry(error, attempt):
                    logger.warning(
                        f"{operation_name} failed and should not retry: {error}"
                    )
                    raise error
                
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}), "
                    f"retrying in {delay}ms: {error}"
                )
                
                await asyncio.sleep(delay / 1000)
                
        raise last_error
    
    def _calculate_delay(self, attempt: int) -> int:
        base_delay = (
            self.options.initial_delay_ms * 
            (self.options.backoff_multiplier ** attempt)
        )
        jitter = base_delay * self.options.jitter_factor * random.random()
        delay_with_jitter = base_delay + jitter
        
        return min(int(delay_with_jitter), self.options.max_delay_ms)


async def with_exponential_backoff(
    operation: Callable[[], Awaitable[T]], 
    options: RetryOptions = None,
    operation_name: str = "operation"
) -> T:
    backoff = ExponentialBackoff(options)
    return await backoff.execute(operation, operation_name)


def sync_exponential_backoff(
    operation: Callable[[], T], 
    options: RetryOptions = None,
    operation_name: str = "operation"
) -> T:
    if options is None:
        options = RetryOptions()
    
    last_error = None
    
    for attempt in range(options.max_retries + 1):
        try:
            if attempt > 0:
                logger.info(
                    f"Retrying {operation_name} (attempt {attempt + 1}/"
                    f"{options.max_retries + 1})"
                )
            
            return operation()
            
        except Exception as error:
            last_error = error
            
            if attempt == options.max_retries:
                logger.error(
                    f"{operation_name} failed after {options.max_retries + 1} "
                    f"attempts: {error}"
                )
                raise error
            
            if not options.should_retry(error, attempt):
                logger.warning(
                    f"{operation_name} failed and should not retry: {error}"
                )
                raise error
            
            base_delay = (
                options.initial_delay_ms * 
                (options.backoff_multiplier ** attempt)
            )
            jitter = base_delay * options.jitter_factor * random.random()
            delay_with_jitter = base_delay + jitter
            delay = min(int(delay_with_jitter), options.max_delay_ms)
            
            logger.warning(
                f"{operation_name} failed (attempt {attempt + 1}), "
                f"retrying in {delay}ms: {error}"
            )
            
            import time
            time.sleep(delay / 1000)
    
    raise last_error
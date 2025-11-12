from functools import lru_cache, wraps
import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pygeoapi.api import APIRequest

LOGGER = logging.getLogger(__name__)


def headers_require_revalidation(request: 'APIRequest') -> bool:
    """Check if request headers indicate caching should be skipped.
    All header comparisons are done case insensitive
    """
    headers: dict = request.headers
    cache_invalidation_headers = {'no-cache', 'no-store', 'must-revalidate'}
    LOGGER.error(headers)
    for header, value in headers.items():
        if header.lower() == 'cache-control':
            for invalidation_header in cache_invalidation_headers:
                if invalidation_header == value.lower():
                    return True

    return False


def lru_cache_specific_args(
    cache_keys: Callable[..., tuple],
    maxsize: int,
    skip_caching_fn: Callable[['APIRequest'], bool] | None = None,
) -> Callable:
    """
    LRU cache where only the computed key participates in caching.
    Parameters
    ----------
    key_func : Callable
        A function which takes the arguments that should be used as the key
        for the lru_cache and returns a tuple of the key arguments
    maxsize : int
        The maximum size of the cache
    skip_caching_fn : Callable[['APIRequest'], bool] | None
        An optional function which takes an APIRequest and returns a boolean
        indicating whether caching should be skipped for the given request.
        Even when skipped, the result will still be stored in the cache.
    Returns
    -------
    Callable
        A decorator function which can be used to cache the results of a method
    """

    def decorator(fn):
        internal_lru_cache = lru_cache(maxsize=maxsize)(
            lambda key: fn(*key_args[key][0], **key_args[key][1])
        )
        key_args = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = cache_keys(*args, **kwargs)

            # Store args/kwargs for this key if not already present
            if key not in key_args:
                key_args[key] = (args, kwargs)

            # Check if caching should be skipped (but still store result)
            if skip_caching_fn:
                request: 'APIRequest' = args[1]
                skip_caching = skip_caching_fn(request)
                if skip_caching:
                    # Execute function directly, bypassing cache lookup
                    result = fn(*args, **kwargs)
                    # Store the result in cache by calling internal_lru_cache
                    # This updates the cache without using the cached value
                    internal_lru_cache(key)
                    return result

            return internal_lru_cache(key)

        # make the wrapper behave like the wrapped lru cache
        wrapper.cache_info = internal_lru_cache.cache_info  # type: ignore
        wrapper.cache_clear = internal_lru_cache.cache_clear  # type: ignore
        return wrapper

    return decorator

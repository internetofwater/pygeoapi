from functools import wraps

from flask import request, g
from flask_caching import Cache
from logging import getLogger

LOGGER = getLogger(__name__)


def cache_flask_view(cache: Cache, server_config: dict):
    def decorator(f):
        # if the resource has not been configured to be cached, then skip it
        def skip_cache():
            view_args = request.view_args or {}
            collection_id = view_args.get("collection_id")
            resources = server_config.get("resources", {})
            collection_cfg = resources.get(collection_id, {})
            return not collection_cfg.get("flask_cache")

        # the full request path with parameters as well as the method is used for the cache key
        # however we do not include headers since those can change between requests
        # without affecting data
        def make_cache_key():
            return f"view/{request.method}/{request.full_path}"
        
        def get_ttl_for_collection_id():
            view_args = request.view_args or {}
            collection_id = view_args.get("collection_id")
            resources = server_config.get("resources", {})
            collection_cfg = resources.get(collection_id, {})
            cache_config = collection_cfg.get("flask_cache", {})
            if "ttl_seconds" not in cache_config:
                raise ValueError(
                    f"'ttl_seconds' not configured in 'flask_cache' config block for {collection_id=}"
                )
            return cache_config["ttl_seconds"]

        @wraps(f)
        def wrapped(*args, **kwargs):
            # if there is no specified collection caching info,
            # it should be fetched fresh and not cached; this is so
            # collections with huge amounts of ids don't get cached
            # implicitly unless the user explicitly configures it
            if skip_cache():
                response = f(*args, **kwargs)
                return response
            
            # if the user has requested no caching, then fetch fresh
            # and refresh the data stored in the cache
            if request.headers.get("Cache-Control") == "no-cache":
                g.cache_hit = False
                response = f(*args, **kwargs)
                cache.set(
                    make_cache_key(), response, timeout=get_ttl_for_collection_id()
                )
                response.headers["Cache-Hit"] = "false"
                return response

            # otherwise check the cache
            cache_key = make_cache_key()
            cached_response = cache.get(cache_key)

            if cached_response is not None:
                g.cache_hit = True
                cached_response.headers["Cache-Hit"] = "true"
                return cached_response
            else:
                LOGGER.debug(f"Cache miss for {cache_key=}")
                g.cache_hit = False
                response = f(*args, **kwargs)
                cache.set(cache_key, response, timeout=get_ttl_for_collection_id())
                response.headers["Cache-Hit"] = "false"
                return response

        return wrapped

    return decorator
from functools import wraps

from flask import request
from flask_caching import Cache

def cache_flask_view(cache: Cache, server_config: dict, default_ttl=60 * 10):
    def decorator(f):
        def skip_cache():
            view_args = request.view_args or {}
            collection_id = view_args.get("collection_id")
            resources = server_config.get("resources", {})
            collection_cfg = resources.get(collection_id, {})
            return collection_cfg.get("flask_cache") is None

        @wraps(f)
        @cache.cached(
            timeout=default_ttl,
            key_prefix=lambda: f"view/{request.method}/{request.full_path}",
            # ideally this would be set to True but there is a bug in the library
            # that makes it always true once it hits once 
            # https://github.com/pallets-eco/flask-caching/pull/579
            # response_hit_indication=True,
            unless=skip_cache,
        )
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapped

    return decorator
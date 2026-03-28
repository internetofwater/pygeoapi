# =================================================================
#
# Authors: Colton Loftus <cloftus@lincolninst.edu>
#
# Copyright (c) 2026 Lincoln Institute Of Land Policy
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================


from flask_caching import Cache
from flask import Flask, request, g
from functools import wraps
import os

import logging


LOGGER = logging.getLogger(__name__)


def make_flask_cache(APP: Flask) -> Cache | None:
    _REDIS_HOST = os.environ.get('REDIS_HOST')
    _REDIS_PORT = os.environ.get('REDIS_PORT')

    if not _REDIS_HOST or not _REDIS_PORT:
        LOGGER.warning("""No redis env vars found.
                       Initializing dummy flask cache without persistence""")
        return Cache(APP, config={'CACHE_TYPE': 'SimpleCache'})
    
    APP.config['CACHE_REDIS_HOST'] = _REDIS_HOST
    APP.config['CACHE_REDIS_PORT'] = _REDIS_PORT
    APP.config['CACHE_TYPE'] = 'RedisCache'
    LOGGER.info('Initializing redis flask cache')

    return Cache(APP)



def cache_flask_view(cache: Cache, server_config: dict,
                     skip_caching_args: list[str] | None = None):
    """
    Decorator to cache flask views

    :param cache: `flask_caching.Cache` instance
    :param server_config: `dict` of server configuration
    :param skip_caching_args: `list` of arguments that when present in
            the request will skip the cache
    """
    def decorator(f):
        # if the resource has not been configured to be cached, then skip it
        def skip_cache():
            if skip_caching_args:
                query_args = request.values
                for arg in skip_caching_args:
                    if arg in query_args:
                        return True

            view_args = request.view_args or {}
            collection_id = view_args.get('collection_id')
            resources = server_config.get('resources', {})
            collection_cfg = resources.get(collection_id, {})
            return not collection_cfg.get('flask_cache')

        # the full request path with parameters as well as the
        # method is used for the cache key however we do not
        # include headers since those can change between requests
        # without affecting data
        def make_cache_key():
            return f'view/{request.method}/{request.full_path}'

        def get_ttl_for_collection_id():
            view_args = request.view_args or {}
            collection_id = view_args.get('collection_id')
            resources = server_config.get('resources', {})
            collection_cfg = resources.get(collection_id, {})
            cache_config = collection_cfg.get('flask_cache', {})
            if 'ttl_seconds' not in cache_config:
                raise ValueError(
                    f"'ttl_seconds' not configured in 'flask_cache'  \
                    config block for {collection_id=}"
                )
            return cache_config['ttl_seconds']

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
                    make_cache_key(), response,
                    timeout=get_ttl_for_collection_id()
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
                cache.set(cache_key, response,
                          timeout=get_ttl_for_collection_id())
                response.headers["Cache-Hit"] = "false"
                return response

        return wrapped

    return decorator

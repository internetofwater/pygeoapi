# =================================================================
#
# Authors: Colton Loftus <cloftus@lincolninst.edu>
#          Ben Webb <bwebb@lincolninst.edu>
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
import logging
import os

from pygeoapi.config import get_config
from pygeoapi.util import get_from_headers


LOGGER = logging.getLogger(__name__)

CONFIG = get_config()
DEFAULT_TTL = os.environ.get('PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS', 3600)


def make_flask_cache(APP: Flask) -> Cache:
    """
    Factory function to create a flask cache instance.

    :param APP: Flask app instance to initialize the cache for

    :returns: A `flask_caching.Cache` instance
    """
    _FLASK_CACHE = os.environ.get('PYGEOAPI_FLASK_CACHE')
    _REDIS_HOST = os.environ.get('PYGEOAPI_REDIS_HOST')
    _REDIS_PORT = os.environ.get('PYGEOAPI_REDIS_PORT')

    if _FLASK_CACHE:
        LOGGER.info(f'Initializing {_FLASK_CACHE} cache')
        return FlaskCache(APP, config={'CACHE_TYPE': 'SimpleCache'})

    elif _REDIS_HOST and _REDIS_PORT:
        LOGGER.info(f'Initializing Redis cache at {_REDIS_HOST}:{_REDIS_PORT}')
        APP.config['CACHE_REDIS_HOST'] = _REDIS_HOST
        APP.config['CACHE_REDIS_PORT'] = _REDIS_PORT
        APP.config['CACHE_TYPE'] = 'RedisCache'
        return FlaskCache(APP)

    else:
        LOGGER.warning('Initializing dummy flask cache without persistence')
        return FlaskCache(APP, config={'CACHE_TYPE': 'NullCache'})


class FlaskCache(Cache):
    def cached_view(
        self,
        skip_caching_args: list[str] | None = None,
        always_cache: bool = False
    ) -> callable:
        """
        Decorator to cache flask views

        :param cache: `flask_caching.Cache` instance
        :param skip_caching_args: `list` of arguments that when present in
                the request will skip the cache
        :param always_cache: if True, the cached view will be not check
                configuration which is useful for `/collections` caching

        :returns: decorated flask view function
        """

        def decorator(f):
            # if the view has not been configured to be cached, skip it
            def skip_cache():
                if always_cache:
                    # attempt to cache the view
                    # will still defer to Cache-Control headers
                    return False

                if skip_caching_args:
                    query_args = request.values
                    for arg in skip_caching_args:
                        if arg in query_args:
                            return True

                view_args = request.view_args or {}
                collection_id = view_args.get('collection_id')
                resources = CONFIG.get('resources', {})
                collection_cfg = resources.get(collection_id, {})
                return not collection_cfg.get('flask_cache')

            # the full request path with parameters as well as the
            # method is used for the cache key however we do not
            # include headers since those can change between requests
            # without affecting data
            def make_cache_key():
                return f'view/{request.method}/{request.full_path}'

            def get_ttl():
                view_args = request.view_args or {}
                collection_id = view_args.get('collection_id')
                resources = CONFIG.get('resources', {})
                collection_cfg = resources.get(collection_id, {})
                cache_config = collection_cfg.get('flask_cache', {})

                if 'ttl_seconds' in cache_config:
                    return cache_config['ttl_seconds']

                LOGGER.warning(
                    f'ttl_seconds not configured for {collection_id=}, '
                    f'defaulting to {DEFAULT_TTL} seconds'
                )
                return DEFAULT_TTL

            @wraps(f)
            def wrapped(*args, **kwargs):
                # if there is no specified collection caching info,
                # it should be fetched fresh and not cached; this is so
                # collections with huge amounts of ids don't get cached
                # implicitly unless the user explicitly configures it
                if skip_cache():
                    response = f(*args, **kwargs)
                    return response

                cache_ttl = get_ttl()
                # if the user has requested no caching, then fetch fresh
                # and refresh the data stored in the cache
                headers = request.headers
                cache_control = get_from_headers(headers, 'cache-control')
                if cache_control == 'no-cache':
                    g.cache_hit = False
                    response = f(*args, **kwargs)
                    self.set(
                        make_cache_key(), response, timeout=cache_ttl
                    )
                    response.headers['Cache-Hit'] = False
                    response.headers['Cache-Control'] = 'no-cache'
                    return response

                # otherwise check the cache
                cache_key = make_cache_key()
                cached_response = self.get(cache_key)

                g.cache_hit = cached_response is not None
                if g.cache_hit:
                    cached_response.headers['Cache-Hit'] = g.cache_hit
                    cached_response.headers['Cache-Control'] = \
                        f'public, s-max-age={cache_ttl}'
                    return cached_response

                else:
                    LOGGER.debug(f'Cache miss for {cache_key=}')
                    response = f(*args, **kwargs)
                    response.headers['Cache-Hit'] = g.cache_hit
                    self.set(cache_key, response, timeout=cache_ttl)
                    return response

            return wrapped

        return decorator

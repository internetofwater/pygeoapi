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


from typing import Callable, Literal, NotRequired, TypedDict

from flask_caching import Cache
from flask import Flask, request, g
from functools import wraps
import logging
import os

from pygeoapi.config import get_config
from pygeoapi.util import get_from_headers


LOGGER = logging.getLogger(__name__)

CONFIG = get_config()


class FlaskCacheConfig(TypedDict):
    """
    The configuration for the flask cache
    within the pygeoapi yml configuration file
    """
    # The time to live of a key / value pair in the cache in seconds
    ttl_seconds: NotRequired[int]
    # Explicitly allow caching on arguments that might otherwise be
    # excluded from caching by the cache configuration
    permit_args: NotRequired[list[str]]


class FlaskCache(Cache):

    collection_id_to_cache_config: dict[str, FlaskCacheConfig]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        resources: dict = CONFIG.get('resources', {})
        # we set the cache config once at initialization
        # which allows for both easier mocking / testing
        # and less config iteration at request-time
        self.collection_id_to_cache_config: dict[str, FlaskCacheConfig] = {
            collection_id: collection_cfg.get('flask_cache')
            for collection_id, collection_cfg in resources.items()
        }

    """Wrapper around to add a decorator for caching OGC API Flask views"""
    def cached_view(
        self,
        skip_caching_args: list[str] | None = None,
        always_cache: bool = False,
    ) -> Callable:
        """
        Decorator to cache flask views

        :param skip_caching_args: `list` of arguments that when present in
            the request will bypass the cache
        :param always_cache: if True, the view will try to cache without
            the pygeoapi configuration for the particular resource;
            This is useful for caching endpoints like `/collections`
            and `/collections/{collection_id}` which contain metadata
            that is not expected to change frequently

        :returns: decorated flask view function
        """

        def get_cache_config_for_request() -> FlaskCacheConfig | None:
            # cache configuration is stored at collection level
            # to allow for caching strategies specific to a collection
            view_args = request.view_args or {}
            collection_id = view_args.get('collection_id')
            if not collection_id:
                return None
            return self.collection_id_to_cache_config.get(collection_id)

        def decorator(f):
            # if the view has not been configured to be cached, skip it
            def skip_cache():
                if always_cache:
                    # attempt to cache the view
                    # will still defer to Cache-Control headers
                    return False

                cache_config = get_cache_config_for_request()
                # if there is no cache config, then we should not cache
                if not cache_config:
                    return True
                if not skip_caching_args:
                    return False
                # allow for a collection to cache on arguments
                # that have been configured to bypass the cache
                # enabling runtime control over cahing without
                # needing to change pygeoapi source code
                query_args = request.values
                permit_args_regardless_of_skip = cache_config.get(
                    'permit_args', []
                )
                for arg_to_skip in skip_caching_args:
                    # if an arg is in the list of args to skip
                    # BUT it is in the list of args to permit regardless
                    # then it does not affect the skip logic
                    if arg_to_skip in permit_args_regardless_of_skip:
                        continue
                    if arg_to_skip in query_args:
                        return True

                return False

            # the full request path with parameters as well as the
            # method is used for the cache key however we do not
            # include headers since those can change between requests
            # without affecting data
            def make_cache_key():
                return f'view/{request.method}/{request.full_path}'

            def get_ttl():
                cache_config = get_cache_config_for_request()
                DEFAULT_TTL = int(
                    os.environ.get('PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS', 3600)
                )
                if not cache_config:
                    return DEFAULT_TTL

                if 'ttl_seconds' not in cache_config:
                    LOGGER.warning(
                        f'ttl_seconds not configured using default of'
                        f'{DEFAULT_TTL} seconds'
                    )

                return cache_config.get('ttl_seconds', DEFAULT_TTL)

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
                headers = dict(request.headers)
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


def make_flask_cache(APP: Flask,
                     cache_type_override:
                     Literal["SIMPLE", "REDIS", "NULL"] |
                     None = None) -> FlaskCache:
    """
    Factory function to create a flask cache instance.

    :param APP: Flask app instance to initialize the cache for
    :param cache_type_override: Optional override for the cache type
        to use a cache type other than the value of PYGEOAPI_FLASK_CACHE_TYPE
        environment variable; useful for testing purposes

    :returns: A `FlaskCache` instance
    """
    if cache_type_override:
        _FLASK_CACHE_TYPE = cache_type_override
    else:
        _FLASK_CACHE_TYPE = os.environ.get('PYGEOAPI_FLASK_CACHE_TYPE')

    match _FLASK_CACHE_TYPE:
        case 'REDIS':
            _REDIS_HOST = os.environ.get('PYGEOAPI_REDIS_HOST')
            _REDIS_PORT = os.environ.get('PYGEOAPI_REDIS_PORT')
            # Redis cache, which maintains global cache state
            # and is good for production deployments, but requires Redis
            if not (_REDIS_HOST and _REDIS_PORT):
                raise ValueError(
                    'Missing host and port vars for REDIS flask cache'
                )

            LOGGER.info(
                f'Initializing REDIS cache at {_REDIS_HOST}:{_REDIS_PORT}'
            )

            APP.config['CACHE_REDIS_HOST'] = _REDIS_HOST
            APP.config['CACHE_REDIS_PORT'] = _REDIS_PORT
            APP.config['CACHE_TYPE'] = 'RedisCache'
            return FlaskCache(APP)

        case 'SIMPLE':
            # Simple cache, which is not shared across threads
            # and processes, but is good for testing and development
            LOGGER.info('Initializing SIMPLE cache')
            return FlaskCache(APP, config={'CACHE_TYPE': 'SimpleCache'})

        case None | 'NULL':
            # Null cache, which does not actually cache anything, but allows
            # the code to run without modification when caching is not desired
            LOGGER.warning('Initializing dummy cache without persistence')
            return FlaskCache(APP, config={'CACHE_TYPE': 'NullCache'})

        case _:
            raise ValueError(f'Undefined Flask Cache type {_FLASK_CACHE_TYPE}')

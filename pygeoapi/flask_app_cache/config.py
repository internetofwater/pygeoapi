import os

from flask_caching import Cache
from flask import Flask

import logging
LOGGER = logging.getLogger(__name__)


def make_flask_cache(APP: Flask) -> Cache:
    _REDIS_HOST = os.environ.get("REDIS_HOST")
    _REDIS_PORT = os.environ.get("REDIS_PORT")

    if _REDIS_HOST and _REDIS_PORT:
        APP.config["CACHE_REDIS_HOST"] = _REDIS_HOST
        APP.config["CACHE_REDIS_PORT"] = _REDIS_PORT
        APP.config["CACHE_TYPE"] = "RedisCache"
        LOGGER.info("Initializing redis flask cache")
    else:
        APP.config["CACHE_TYPE"] = "NullCache"

    return Cache(APP)

import os

from flask_caching import Cache 
from pygeoapi.flask_app import APP

_REDIS_HOST = os.environ.get("REDIS_HOST")
_REDIS_PORT = os.environ.get("REDIS_PORT")

if _REDIS_HOST and _REDIS_PORT:
    APP.config["CACHE_REDIS_HOST"] = _REDIS_HOST
    APP.config["CACHE_REDIS_PORT"] = _REDIS_PORT
    APP.config["CACHE_TYPE"] = "RedisCache"
else:
    APP.config["CACHE_TYPE"] = "NullCache"

FLASK_APP_CACHE = Cache(APP)

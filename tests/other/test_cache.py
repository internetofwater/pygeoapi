import os
from flask import Flask, Response
import pytest
from time import sleep

from tests.util import mock_flask
from pygeoapi.flask_app.cache import make_flask_cache


def test_api_no_cache(api_):

    os.environ['PYGEOAPI_FLASK_CACHE_TYPE'] = 'NULL'
    os.environ['PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS'] = '1'

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

        sleep(2)

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers


def test_api_simple_cache(api_):

    os.environ['PYGEOAPI_FLASK_CACHE_TYPE'] = 'SIMPLE'
    os.environ['PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS'] = '1'

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'True'
        assert 'Cache-Control' in response.headers

        sleep(2)

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers


def test_api_invalid_cache(api_):
    # Test API with invalid cache variables
    os.environ['PYGEOAPI_FLASK_CACHE_TYPE'] = 'INVALID'

    with pytest.raises(ValueError):
        with mock_flask('pygeoapi-test-config.yml') as flask_client:
            flask_client.get('/collections/obs')


def test_cache_object_directly():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override="SIMPLE")

    call_count = {"count": 0}

    def test_func():
        call_count["count"] += 1
        return Response("ok")

    wrapped = flask_cache.cached_view(always_cache=True)(test_func)

    # simulate a request context
    with flask_app.test_request_context("/test"):
        # first call cache miss
        resp1 = wrapped()
        assert resp1.data == b"ok"
        assert call_count["count"] == 1
        assert resp1.headers["Cache-Hit"] == "False"

        # second call cache hit (should NOT call function again)
        resp2 = wrapped()
        assert resp2.data == b"ok"
        assert call_count["count"] == 1
        assert resp2.headers["Cache-Hit"] == "True"


def test_cache_control_header():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override="SIMPLE")

    call_count = {"count": 0}

    def test_func():
        call_count["count"] += 1
        return Response("fresh")

    # we set always cache = true so we don't have to check the CONFIG
    # variable for the cache config values
    wrapped = flask_cache.cached_view(
        always_cache=True)(test_func)

    with flask_app.test_request_context("/test",
                                        headers={"Cache-Control": "no-cache"}):
        resp = wrapped()
        assert resp.headers["Cache-Control"] == "no-cache"
        assert call_count["count"] == 1

    # second request without header should hit cache
    with flask_app.test_request_context("/test"):
        resp = wrapped()
        assert call_count["count"] == 1
        assert resp.headers["Cache-Hit"] == "True"


def test_skip_caching_args_bypasses_cache():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override="SIMPLE")

    call_count = {"count": 0}

    def test_func():
        call_count["count"] += 1
        return Response("data")

    wrapped = flask_cache.cached_view(skip_caching_args=["q"])(
        test_func
    )

    # request includes ?q=123 should skip cache
    # since it was one of the `skip_caching_args` specified above
    with flask_app.test_request_context("/test?q=123"):
        wrapped()
        wrapped()

    # function should be called twice (no caching)
    assert call_count["count"] == 2


def test_collection_items_permit_args():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override="SIMPLE")

    flask_cache.collection_id_to_cache_config["foo"] = {
        "permit_args": ["bbox"]}

    call_count = {"count": 0}

    @flask_app.route("/collections/<path:collection_id>/items")
    @flask_cache.cached_view(skip_caching_args=["bbox"])
    def route(collection_id):
        call_count["count"] += 1
        return Response("data")

    client = flask_app.test_client()

    # bbox present and normally would be bypassed, but when
    # explicitly permitted should cache
    client.get("/collections/foo/items?bbox=1,2,3,4")
    client.get("/collections/foo/items?bbox=1,2,3,4")

    assert call_count["count"] == 1

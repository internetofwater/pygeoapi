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


import os
from flask import Flask, Response, request
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
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    call_count = {'count': 0}

    def test_func():
        call_count['count'] += 1
        return Response('ok')

    wrapped = flask_cache.cached_view(always_cache=True)(test_func)

    # simulate a request context
    with flask_app.test_request_context('/test'):
        # first call cache miss
        resp1 = wrapped()
        assert resp1.data == b'ok'
        assert call_count['count'] == 1
        assert resp1.headers['Cache-Hit'] == 'False'

        # second call cache hit (should NOT call function again)
        resp2 = wrapped()
        assert resp2.data == b'ok'
        assert call_count['count'] == 1
        assert resp2.headers['Cache-Hit'] == 'True'


def test_cache_control_header():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    call_count = {'count': 0}

    def test_func():
        call_count['count'] += 1
        return Response('fresh')

    # we set always cache = true so we don't have to check the CONFIG
    # variable for the cache config values
    wrapped = flask_cache.cached_view(
        always_cache=True)(test_func)

    with flask_app.test_request_context(
        '/test',
        headers={'Cache-Control': 'no-cache'}
    ):
        resp = wrapped()
        assert resp.headers['Cache-Control'] == 'no-cache'
        assert call_count['count'] == 1

    # second request without header should hit cache
    with flask_app.test_request_context('/test'):
        resp = wrapped()
        assert call_count['count'] == 1
        assert resp.headers['Cache-Hit'] == 'True'


def test_skip_caching_args_bypasses_cache():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    call_count = {'count': 0}

    def test_func():
        call_count['count'] += 1
        return Response('data')

    wrapped = flask_cache.cached_view(skip_caching_args=['q'])(
        test_func
    )

    # request includes ?q=123 should skip cache
    # since it was one of the `skip_caching_args` specified above
    with flask_app.test_request_context('/test?q=123'):
        wrapped()
        wrapped()

    # function should be called twice (no caching)
    assert call_count['count'] == 2


def test_collection_items_permit_args():
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    flask_cache.collection_id_to_cache_config['foo'] = {
        'permit_args': ['bbox']}

    call_count = {'count': 0}

    @flask_app.route('/collections/<path:collection_id>/items')
    @flask_cache.cached_view(skip_caching_args=['bbox'])
    def route(collection_id):
        call_count['count'] += 1
        return Response('data')

    client = flask_app.test_client()

    # bbox present and normally would be bypassed, but when
    # explicitly permitted should cache
    client.get('/collections/foo/items?bbox=1,2,3,4')
    client.get('/collections/foo/items?bbox=1,2,3,4')

    assert call_count['count'] == 1


def test_accept_headers_included_in_cache():
    '''Test that Accept headers are considered when caching responses.'''
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    call_count = {'count': 0}

    def test_func():
        call_count['count'] += 1
        # Return different content based on Accept header
        if request.headers.get('Accept') == 'application/json':
            return Response(
                "{'data': 'json'}", content_type='application/json'
            )
        else:
            return Response(
                '<html><body>html</body></html>', content_type='text/html'
            )

    wrapped = flask_cache.cached_view(always_cache=True)(test_func)

    # First request with JSON Accept header
    with flask_app.test_request_context(
        '/test', headers={'Accept': 'application/json'}
    ):
        resp1 = wrapped()
        assert resp1.data == b"{'data': 'json'}"
        assert resp1.content_type == 'application/json'
        assert call_count['count'] == 1
        assert resp1.headers['Cache-Hit'] == 'False'

    # Second request with same JSON Accept header should hit cache
    with flask_app.test_request_context(
        '/test', headers={'Accept': 'application/json'}
    ):
        resp2 = wrapped()
        assert resp2.data == b"{'data': 'json'}"
        assert resp2.content_type == 'application/json'
        assert call_count['count'] == 1  # Should not increment
        assert resp2.headers['Cache-Hit'] == 'True'

    # Third request with different Accept header should
    # miss cache and call function
    with flask_app.test_request_context(
        '/test', headers={'Accept': 'text/html'}
    ):
        resp3 = wrapped()
        assert resp3.data == b'<html><body>html</body></html>'
        assert resp3.content_type == 'text/html'
        assert call_count['count'] == 2  # Should increment
        assert resp3.headers['Cache-Hit'] == 'False'

    # Fourth request with HTML Accept header should hit cache
    with flask_app.test_request_context(
        '/test', headers={'Accept': 'text/html'}
    ):
        resp4 = wrapped()
        assert resp4.data == b'<html><body>html</body></html>'
        assert resp4.content_type == 'text/html'
        assert call_count['count'] == 2  # Should not increment
        assert resp4.headers['Cache-Hit'] == 'True'


def test_digest_header_skips_cache():
    '''Test that digest headers are excluded from cache key generation.

    This ensures that requests with different digest headers still hit
    the same cache entry, as digest headers should not affect caching.
    '''
    flask_app = Flask(__name__)
    flask_cache = make_flask_cache(flask_app, cache_type_override='SIMPLE')

    call_count = {'count': 0}

    def test_func():
        call_count['count'] += 1
        return Response(str(call_count['count']))

    wrapped = flask_cache.cached_view(always_cache=True)(test_func)

    # Lastly request without digest header
    with flask_app.test_request_context('/test'):
        resp1 = wrapped()
        assert resp1.data == b'1'
        assert call_count['count'] == 1
        assert resp1.headers['Cache-Hit'] == 'False'

    # Second request with digest header should still hit cache
    # (digest headers should be ignored in cache key generation)
    with flask_app.test_request_context(
        '/test',
        headers={'Want-Content-Digest': 'SHA256'}
    ):
        resp2 = wrapped()
        assert resp2.data == b'2'
        assert call_count['count'] == 2  # Should increment

    # Third request with different digest header should also hit cache
    with flask_app.test_request_context(
        '/test',
        headers={'Want-Content-Digest': 'SHA256'}
    ):
        resp3 = wrapped()
        assert resp3.data == b'3'
        assert call_count['count'] == 3  # Should increment

    # Last request without digest headern (cache hit from first request)
    with flask_app.test_request_context('/test'):
        resp1 = wrapped()
        assert resp1.data == b'1'
        assert call_count['count'] == 3  # Should not increment
        assert resp1.headers['Cache-Hit'] == 'True'

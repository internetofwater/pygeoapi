import os
import pytest
from time import sleep

from tests.util import (get_test_file_path, mock_api_request, mock_flask,
                        mock_starlette, mock_request)

def test_api_no_cache(api_):

    os.environ['PYGEOAPI_FLASK_CACHE_TYPE'] = 'Null'
    os.environ['PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS'] = '1'

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

        sleep(1)

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

        sleep(1)

        response = flask_client.get('/collections/obs')
        assert response.headers['Cache-Hit'] == 'False'
        assert 'Cache-Control' not in response.headers

def test_api_invalid_cache(api_):
    
    os.environ['PYGEOAPI_FLASK_CACHE_TYPE'] = 'INVALID'
    os.environ['PYGEOAPI_DEFAULT_CACHE_TTL_SECONDS'] = '1'

    with pytest.raises(ValueError):
        with mock_flask('pygeoapi-test-config.yml') as flask_client:
            flask_client.get('/collections/obs')

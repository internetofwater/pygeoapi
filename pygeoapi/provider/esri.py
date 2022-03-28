# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2022 Benjamin Webb
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

from requests import Session, codes
import logging
from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError)
from json.decoder import JSONDecodeError
from pygeoapi.util import format_datetime

LOGGER = logging.getLogger(__name__)


class ESRIServiceProvider(BaseProvider):
    """ESRI Feature/Map Service Provider
    """

    def __init__(self, provider_def):
        """
        ESRI Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data, id_field, name set in parent class

        :returns: pygeoapi.provider.esri.ESRIServiceProvider
        """
        LOGGER.debug("Logger ESRI Init")

        super().__init__(provider_def)
        self._url = f'{self.data}/query'
        self._token = ''
        self._username = provider_def.get('username')
        self._password = provider_def.get('password')
        self.get_fields()
        self.numFeatures = self.query(
            resulttype='hits').get('numberMatched')

    def get_fields(self):
        """
         Get fields of ESRI Provider

        :returns: dict of fields
        """

        if not self.fields:
            # Start session
            s = Session()

            # Generate token from username and password
            if self._username and self._password and self._token == '':
                params = {
                    'f': 'pjson',
                    'username': self._username,
                    'password': self._password,
                    'referer': 'http://www.arcgis.com/'
                }

                url = 'https://www.arcgis.com/sharing/rest/generateToken'
                with s.post(url, data=params) as r:
                    self._token = r.json().get('token', '')

            # Load fields
            params = {
                'f': 'pjson',
                'token': self._token
            }
            try:
                with s.get(self.data, params=params) as r:
                    resp = r.json()
            except JSONDecodeError as err:
                LOGGER.error('Bad response at {}'.format(self.data))
                raise ProviderQueryError(err)

            # Verify Feature/Map Service supports required capabilities
            advCapabilities = resp['advancedQueryCapabilities']
            if advCapabilities['supportsPagination'] is False \
                    or advCapabilities['supportsOrderBy'] is False \
                    or 'geoJSON' not in resp['supportedQueryFormats']:
                raise ProviderConnectionError(
                    'Unsupported Feature/Map Server')

            for _ in resp['fields']:
                self.fields.update({_['name']: {'type': _['type']}})

        return self.fields

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        ESRI query

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(offset, limit, resulttype, bbox=bbox,
                          datetime_=datetime_, properties=properties,
                          sortby=sortby, select_properties=select_properties,
                          skip_geometry=skip_geometry)

    def get(self, identifier, **kwargs):
        """
        Query ESRI by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        return self._load(identifier=identifier)

    def _load(self, offset=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime_=None, properties=[],
              sortby=[], select_properties=[], skip_geometry=False, q=None):
        """
        Private function: Load ESRI data

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param identifier: feature id (get collections item)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: dict of GeoJSON FeatureCollection
        """

        # Default feature collection and request parameters
        fc = {
            'type': 'FeatureCollection',
            'features': []
        }
        params = {
            'f': 'geoJSON',
            'outSR': '4326',
            'resultOffset': offset,
            'resultRecordCount': limit,
            'where': '1=1',
        }

        if not self.properties and not select_properties:
            params['outFields'] = '*'
        else:
            params['outFields'] = set(self.properties) | set(select_properties)

        if identifier:
            # Add feature id to request params
            params['objectIds'] = identifier

        else:
            # Add queryables to request params
            if properties or datetime_:
                params['where'] = self._make_where(properties, datetime_)

            if bbox:
                params['inSR'] = '4326'
                params['geometryType'] = 'esriGeometryEnvelope'
                xmin, ymin, xmax, ymax = bbox
                params['geometry'] = f'{xmin},{ymin},{xmax},{ymax}'

            if resulttype == 'hits':
                params['returnCountOnly'] = 'true'
                params['resultRecordCount'] = ''

            if sortby:
                params['orderByFields'] = self._make_orderby(sortby)

            if skip_geometry:
                params['returnGeometry'] = 'false'

        # Add token to tail
        params['token'] = self._token

        # Start session
        s = Session()

        # Form URL for GET request
        LOGGER.debug('Sending query')
        with s.get(self._url, params=params) as r:

            if r.status_code == codes.bad:
                LOGGER.error('Bad http response code')
                raise ProviderConnectionError('Bad http response code')

            resp = r.json()

        if identifier:
            # Return single feature
            fc = resp['features'].pop()

        elif resulttype == 'hits':
            # Return hits
            LOGGER.debug('Returning hits')
            hits = resp.get('count',
                            resp.get('properties', {}).get('count', 0))
            fc['numberMatched'] = hits

        else:
            # Return feature collection
            v = resp.get('features')
            step = len(v)
            hits_ = min(limit, self.numFeatures)

            # Query if values are less than expected
            while len(v) < hits_:
                LOGGER.debug('Fetching next set of values')
                params['resultOffset'] += step
                params['resultRecordCount'] += step
                with s.get(self._url, params=params) as r:
                    response = r.json()
                    v.extend(response.get('features'))

            fc['features'] = v
            fc['numberReturned'] = len(v)

        # End session
        s.close()

        return fc

    @staticmethod
    def _make_orderby(sortby):
        """
        Private function: Make ESRI filter from query properties

        :param sortby: `list` of dicts (property, order)

        :returns: ESRI query `order` clause
        """
        __ = {'+': 'ASC', '-': 'DESC'}
        ret = [f"{_['property']} {__[_['order']]}" for _ in sortby]

        return ','.join(ret)

    @staticmethod
    def esri_date(dt):
        """
        Private function: Make ESRI filter from query properties

        :param dt:  `str` of ISO datetime

        :returns: ESRI query `order` clause
        """
        dt = format_datetime(dt).replace('T', ' ').replace('Z', '')
        return f"DATE '{dt}'"

    def _make_where(self, properties, datetime_=None):
        """
        Private function: Make ESRI filter from query properties

        :param properties: `list` of tuples (name, value)
        :param datetime_: `str` temporal (datestamp or extent)

        :returns: ESRI query `where` clause
        """

        p = []

        if properties:

            for (k, v) in properties:
                if 'String' in self.fields[k]['type']:
                    p.append(f"{k} = '{v}'")
                else:
                    p.append(f"{k} = {v}")

        if datetime_:

            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                if time_start != '..':
                    p.append(
                        f"{self.time_field} >= {self.esri_date(time_start)}")
                if time_end != '..':
                    p.append(
                        f'{self.time_field} <= {self.esri_date(time_end)}')
            else:
                p.append(f'{self.time_field} = {self.esri_date(datetime_)}')

        return ' AND '.join(p)

    def __repr__(self):
        return '<ESRIProvider> {}'.format(self.data)

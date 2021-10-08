# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
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
import logging
from requests import get
from shapely.geometry.multilinestring import MultiLineString
from shapely import speedups

from pygeoapi.util import yaml_load, url_join
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError


LOGGER = logging.getLogger(__name__)
CONFIG_ = ''
P = 'properties'
LOGGER.debug('Shapely speedups {}'.format(speedups.enabled))

with open(os.getenv('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG_ = yaml_load(fh)

PROVIDER = CONFIG_['resources']['merit']['providers'][0]

PROCESS_DEF = CONFIG_['resources']['river-runner']
PROCESS_DEF.update({
    'version': '0.5.0',
    'id': 'river-runner',
    'inputs': {
        'bbox': {
            'title': {
                'en': 'Bounding Box'
            },
            'description': {
                'en': 'Boundary box to begin a river runner query'
            },
            'keywords': {
                'en': ['bounding', 'box', 'coordinates']
            },
            'schema': {
                'type': 'object',
                'default': ['minLng', 'minLat', 'maxLng', 'maxLat']
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'lat': {
            'title': {
                'en': 'Latitude'
            },
            'description': {
                'en': 'Latitude coordinate of a point'
            },
            'keywords': {
                'en': ['latitude', 'eastwest', 'coordinate']
            },
            'schema': {
                'type': 'number',
                'default': None
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'lng': {
            'title': {
                'en': 'Longitude'
            },
            'description': {
                'en': 'Longitude coordinate of a point'
            },
            'keywords': {
                'en': ['longitude', 'northsouth', 'coordinate']
            },
            'schema': {
                'type': 'number',
                'default': None
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'latlng': {
            'title': {
                'en': 'Latitude and Longitude'
            },
            'description': {
                'en': 'Lat and Lng coordinates in order [lng,lat]'
            },
            'keywords': {
                'en': ['latitude', 'longitude', 'coordinates']
            },
            'schema': {
                'type': 'object',
                'default': ['lng', 'lat']
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'id': {
            'title': {
                'en': 'OGC Feature Identifier'
            },
            'description': {
                'en': 'Identifier of starting feature'
            },
            'keywords': {
                'en': ['feature', 'ogc', 'id', 'identifier']
            },
            'schema': {
                'type': 'number',
                'default': ''
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'sorted': {
            'title': {
                'en': 'Sorted'
            },
            'description': {
                'en': 'Sort features by flow direction'
            },
            'keywords': {
                'en': ['downstream', 'upstream', 'unset']
            },
            'schema': {
                'type': 'string',
                'default': 'downstream'
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'sortby': {
            'title': {
                'en': 'Sort By'
            },
            'description': {
                'en': 'Property by which to sort features'
            },
            'keywords': {
                'en': ['sort', 'comid', 'hydroseq']
            },
            'schema': {
                'type': 'string',
                'default': 'hydroseq'
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        },
        'groupby': {
            'title': {
                'en': 'Group By'
            },
            'description': {
                'en': 'Properties by which to group features'
            },
            'keywords': {
                'en': ['group', 'nameid', 'streamlev']
            },
            'schema': {
                'type': ['string', 'list'],
                'default': None
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
        }
    },
    'outputs': {
        'path': {
            'title': {
                'en': 'FeatureCollection'
            },
            'description': {
                'en': 'A geoJSON FeatureCollection of the '\
                      'path generated by the river runner process'
            },
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json'
            }
        }
    },
    'example': {
        'inputs': {
            'bbox': [-86.2, 39.7, -86.15, 39.75],
            'sorted': 'downstream',
            'groupby': 'nameid,streamlev,levelpathi'
        }
    }
})


class RiverRunnerProcessor(BaseProcessor):
    """River Runner Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.river_runner.RiverRunnerProcessor
        """
        super().__init__(processor_def, PROCESS_DEF)

    def execute(self, data):
        """
        Execute River Runner Process

        :param data: processor arguments

        :returns: 'application/json'
        """
        mimetype = 'application/json'
        outputs = {
                'id': 'path',
                'code': 'success',
                'value': {
                    'type': 'FeatureCollection',
                    'features': []
                }
            }

        groupby = data.get('groupby', '')
        if groupby:
            data['sortby'] = 'hydroseq'
            data['sorted'] = 'downstream'
        order = self._make_order(data)

        LOGGER.debug('Fetching first feature')
        if data.get('id', None):
            outputs['value'] = self._from_fid(data.pop('id'), order)
        else:
            if not data.get('bbox') and not data.get('latlng') and \
               (not data.get('lat') and not data.get('lng')):
                raise ProcessorExecuteError(f'Invalid input: {data.items()}')

            f = self._from_bbox(self._make_bbox(data))
            if not f:
                outputs['code'] = 'fail'
                return mimetype, outputs

            url = url_join(
                CONFIG_['server']['url'],
                'processes/river-runner/execution'
                )
            r = get(url, params={'id': f['id']})
            outputs['value'] = r.json().get('value')

        if groupby:
            outputs['value'] = self._group_by(outputs['value'], groupby)

        return mimetype, outputs

    def _from_fid(self, fid, order):
        """
        Private Function: Use ogc_fid for start feature of river runner

        :param fid: feature id
        :param order: OGC API sortby parameter

        :returns: GeoJSON Feature Collection
        """
        p = load_plugin('provider', PROVIDER)
        feature = p.get(fid)

        LOGGER.debug('fetching downstream features')
        levelpaths = self._levelpaths(feature)

        d = p.query(
                properties=[('levelpathi', i) for i in levelpaths],
                sortby=order,
                limit=10000,
                comp='OR'
                )

        LOGGER.debug('finding mins')
        mins = {level: {} for level in levelpaths}
        for f in d['features']:
            key = str(f[P]['levelpathi'])
            prev = mins[key].get(P, {}).get('hydroseq', None)

            if prev is None or \
               min(prev, f[P]['hydroseq']) != prev:
                mins[key] = f

        trim = [(feature[P]['levelpathi'], feature[P]['hydroseq'])]
        for v in mins.values():
            trim.append((v[P]['dnlevelpat'], v[P]['dnhydroseq']))

        LOGGER.debug('keeping only mainstem flowpath')
        outm = []
        for f in d['features']:
            for t in trim:
                if f[P]['levelpathi'] == t[0] and \
                   f[P]['hydroseq'] <= t[1]:
                    outm.append(f)
        d['features'] = outm
        return d

    def _from_bbox(self, bbox, n=3, delta=0.05):
        """
        Private Function: Use bbox for start feature of river runner

        :param bbox: boundary box
        :param n: number of loops
        :param delta: degrees to expand bbox by

        :returns: GeoJSON feature
        """
        p = load_plugin('provider', PROVIDER)
        value = p.query(bbox=bbox)

        attempts = 1
        while len(value['features']) < 1 and attempts < n:
            LOGGER.debug(f'No features in bbox {bbox}, expanding')
            bbox = self._expand_bbox(bbox, e=delta)
            value = p.query(bbox=bbox)
            attempts += 1

        if len(value['features']) < 1:
            LOGGER.debug('No features found')
            return

        return self._compare(value, 'hydroseq', min)

    def _make_bbox(self, data):
        """
        Private Function: Make Boundary box from query parameters

        :param data: processor arguments

        :returns: OGC API bbox parameter
        """
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = ','.join(v.split(',')).strip('()[]')
                if k in ['latlng', 'bbox']:
                    data[k] = data[k].split(',')

        if data.get('bbox', data.get('latlng')):
            bbox = data.get('bbox', data.get('latlng'))
        else:
            bbox = (data.get('lng'), data.get('lat'))

        bbox = bbox * 2 if len(bbox) == 2 else bbox
        return self._expand_bbox(bbox)

    def _make_order(self, data):
        """
        Private Function: Make sortby from query parameters

        :param data: processor arguments

        :returns: OGC API sortby parameter
        """
        order = data.get('sorted', 'downstream')
        if order and order not in ['unsorted', 'unset']:
            keys = {'downstream': '-', 'upstream': '+'}
            sortprop = data.get('sortby', 'hydroseq')
            order = [{'property': sortprop, 'order': keys[order]}]
            return order
        else:
            return []

    def _levelpaths(self, mh):
        """
        Private Function: Fetch downstream levelpathi's

        :param mh: GeoJSON feature

        :returns: list of downstream feature levelpathi's
        """
        levelpaths = []
        for i in (mh[P]['levelpathi'],
                  *mh[P]['down_levelpaths'].split(',')):
            try:
                levelpaths.append(str(int(float(i))))
            except ValueError:
                LOGGER.debug('No Downstem Rivers found')
        return levelpaths

    def _compare(self, fc, prop, dir):
        """
        Private Function: Find min/max of a FeatureCollection

        :param fc: GeoJSON FeatureCollection
        :param prop: property to sort by
        :param dir: min or max comparator

        :returns: feature with min/max value of prop
        """
        val = fc['features'][0]
        for f in fc['features']:
            if dir(f[P][prop], val[P][prop]) != val[P][prop]:
                val = f
        return val

    def _expand_bbox(self, bbox, e=0.025):
        """
        Private Function: Expand and sort bbox

        :param bbox: Boundary Box in
        :param e: distance to expand bbox

        :returns: OGC API bbox
        """
        def bound(coords, b, dir):
            return dir(map(lambda c: (c + b) % (b * 2) - b, coords))

        bbox = [float(b) + e if i < 2 else float(b) - e
                for (i, b) in enumerate(bbox)]
        return [bound(bbox[::2], 180, min), bound(bbox[1::2], 90, min),
                bound(bbox[::2], 180, max), bound(bbox[1::2], 90, max)]

    def _group_by(self, fc, groupby):
        """
        Private Function: Merge features into multiline string

        :param fc: GeoJSON Feature Collection
        :param groupby: parameter to group on

        :returns: list of merged features
        """
        if isinstance(groupby, str):
            groupby = groupby.strip('()[]').split(',')
        LOGGER.debug(groupby)

        groups = []
        prev = {P: {gb: None for gb in groupby}}
        for (i, f) in enumerate(fc['features']):
            gbs = [f[P][gb] for gb in groupby]
            prevs = [prev[P][gb] for gb in groupby]
            prev = f
            same = True

            for (_gb, _prevgb) in zip(gbs, prevs):
                same = True if _gb == _prevgb and same is True else False

            groups[-1].update({'end': i+1}) if same is True else \
                groups.append({'start': i, 'end': i+1})

        LOGGER.debug(groups)
        out_features = []
        for val in groups:
            start = val['start']
            end = val['end']
            geo = [f['geometry']['coordinates']
                   for f in fc['features'][start:end]]
            geom = MultiLineString(geo)

            feature = fc['features'][end-1]
            feature['geometry']['type'] = geom.geom_type
            feature['geometry']['coordinates'] = \
                [p.coords[:] for p in geom.geoms]

            keys = [*feature[P].keys()]
            for k in keys:
                if k not in groupby:
                    feature[P].pop(k)
            out_features.append(feature)

        fc['features'] = out_features
        return fc

    def __repr__(self):
        return '<RiverRunnerProcessor> {}'.format(self.name)

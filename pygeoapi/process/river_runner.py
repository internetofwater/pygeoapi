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
from shapely.geometry.multilinestring import MultiLineString

from pygeoapi.util import yaml_load
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError


LOGGER = logging.getLogger(__name__)
CONFIG_ = ''
P = 'properties'

with open(os.getenv('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG_ = yaml_load(fh)

PROVIDER_DEF = CONFIG_['resources']['merit']['providers'][0]
PROCESS_DEF = CONFIG_['resources']['river-runner']
PROCESS_DEF.update({
    'version': '0.1.0',
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
                'en': 'Property by which to group features'
            },
            'keywords': {
                'en': ['group', 'nameid', 'streamlev']
            },
            'schema': {
                'type': 'string',
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
            'sorted': 'downstream'
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

        :returns: 'application/json', outputs
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

        if not data.get('bbox') and not data.get('latlng') and \
           (not data.get('lat') and not data.get('lng')):
            raise ProcessorExecuteError(f'Invalid input: { {{data.items()}} }')

        bbox = self._make_bbox(data)
        order = self._make_order(data)
        groupby = data.get('groupby', '')
        if groupby:
            data['sortby'] = groupby
            data['sorted'] = 'downstream'
            order = self._make_order(data)

        p = load_plugin('provider', PROVIDER_DEF)
        value = p.query(bbox=bbox, sortby=order)

        if len(value['features']) < 1:
            LOGGER.debug(f'No features in bbox {bbox}, expanding')
            bbox = self._expand_bbox(bbox, e=1)
            value = p.query(bbox=bbox, sortby=order)

            if len(value['features']) < 1:
                LOGGER.debug('No features found')
                return mimetype, outputs

        LOGGER.debug('fetching downstream features')
        mh = self._compare(value, 'hydroseq', min)
        levelpaths = self._levelpaths(mh)

        d = p.query(
                properties=[('levelpathi', i) for i in levelpaths],
                sortby=order, limit=10000, comp='OR'
                )

        mins = {level: {} for level in levelpaths}
        for f in d['features']:
            key = str(f[P]['levelpathi'])
            prev = mins[key].get(P, {}).get('hydroseq', None)

            if prev is None or \
               min(prev, f[P]['hydroseq']) != prev:
                mins[key] = f

        trim = [(mh[P]['levelpathi'], mh[P]['hydroseq'])]
        for v in mins.values():
            trim.append((v[P]['dnlevelpat'], v[P]['dnhydroseq']))

        LOGGER.debug('keeping only mainstem flowpath')
        outm = []
        for f in d['features']:
            for t in trim:
                if f[P]['levelpathi'] == t[0] and \
                   f[P]['hydroseq'] <= t[1]:
                    outm.append(f)

        if groupby in p.get_fields():
            outm = self._group_by(outm, groupby)

        value['features'] = outm
        outputs.update({'value': value})
        return mimetype, outputs

    def _make_bbox(self, data):
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
        order = data.get('sorted', [])
        if order and order not in ['unsorted', 'unset']:
            keys = {'downstream': '-', 'upstream': '+'}
            sortprop = data.get('sortby', 'hydroseq')
            order = [{'property': sortprop, 'order': keys[order]}]
        return order

    def _levelpaths(self, mh):
        levelpaths = []
        for i in (mh[P]['levelpathi'],
                  *mh[P]['down_levelpaths'].split(',')):
            try:
                levelpaths.append(str(int(float(i))))
            except ValueError:
                LOGGER.debug(f'No Downstem Rivers found {i}')
        return levelpaths

    def _compare(self, fc, prop, dir):
        val = fc['features'][0]
        for f in fc['features']:
            if dir(f[P][prop], val[P][prop]) != val[P][prop]:
                val = f
        return val

    def _expand_bbox(self, bbox, e=0.25):
        def bound(coords, b, dir):
            return dir(map(lambda c: (c + b) % (b * 2) - b, coords))

        bbox = [float(b) + e if i < 2 else float(b) - e
                for (i, b) in enumerate(bbox)]
        return [bound(bbox[::2], 180, min), bound(bbox[1::2], 90, min),
                bound(bbox[::2], 180, max), bound(bbox[1::2], 90, max)]

    def _group_by(self, features, groupby):

        out_features = []
        groups = {}
        # counter = 0
        for (i, f) in enumerate(features):
            # if name in groups.keys() and \
            #    f[P][groupby] != features[i-1][P][groupby]:
            #     name = f'{f[P][groupby]}_{counter}'
            #     counter += 1
            name = f[P][groupby]
            if name not in groups.keys():
                groups[name] = {'start': i, 'end': i+1}
            else:
                groups[name]['end'] = i+1

        LOGGER.debug(groups)
        for val in groups.values():
            # bound = False
            # for other in groups.values():
            #     if val['start'] > other['start'] and\
            #        val['end'] < other['end']:
            #         bound = True
            # if bound is True:
            #     LOGGER.debug(val)
            #     continue

            start = val['start']
            end = val['end']

            feature = features[start]
            geo = [feature['geometry']['coordinates'], ]
            for f in features[start:end]:
                geo.append(
                    f['geometry']['coordinates']
                )
                feature[P] = f[P]

            geom = MultiLineString(geo)
            feature['geometry']['type'] = geom.geom_type
            feature['geometry']['coordinates'] = \
                [p.coords[:] for p in geom.geoms]

            out_features.append(feature)

        return out_features

    def __repr__(self):
        return '<RiverRunnerProcessor> {}'.format(self.name)

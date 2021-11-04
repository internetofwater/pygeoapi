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

from pygeoapi.util import yaml_load
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError


LOGGER = logging.getLogger(__name__)
CONFIG = ''

with open(os.getenv('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

PROVIDER_DEF = CONFIG['resources']['merit']['providers'][0]
P = 'properties'
#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.1.0',
    'id': 'river-runner',
    'title': {
        'en': 'River Runner'
    },
    'description': {
        'en': 'A simple process that takes a lat/long as input, and returns '
              'it back as output. Intended to demonstrate a simple '
              'process with a single literal input.'
    },
    'keywords': ['river runner', 'rivers'],
    'links': [{
        'type': 'text/html',
        'rel': 'canonical',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'bbox': {
            'title': 'Boundary Box',
            'description': 'A set of four coordinates',
            'schema': {
                'type': 'object',
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['coordinates', 'geography']
        },
        'lat': {
            'title': 'Latitude',
            'description': 'Latitude of a point',
            'schema': {
                'type': 'number',
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['coordinates', 'longitude']
        },
        'long': {
            'title': 'Longitude',
            'description': 'Longitude of a point',
            'schema': {
                'type': 'number',
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['coordinates', 'latitude']
        }
    },
    'outputs': {
        'echo': {
            'title': 'Feature Collection',
            'description': 'A geoJSON Feature Collection of River Runner',
            'schema': {
                'type': 'Object',
                'contentMediaType': 'application/json'
            }
        }
    },
    'example': {
        'inputs': {
            'bbox': [-86.2, 39.7, -86.15, 39.75]
        }
    }
}


class RiverRunnerProcessor(BaseProcessor):
    """River Runner Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.river_runner.RiverRunnerProcessor
        """
        self.p = load_plugin('provider', PROVIDER_DEF)
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):
        mimetype = 'application/json'
        if len(data.get('bbox', [])) != 4 and \
           not data.get('lat', '') and \
           not data.get('long', ''):
            raise ProcessorExecuteError('Cannot process without any input')

        if data.get('bbox', []):
            bbox = data['bbox']
        else:
            bbox = (data['lat'], data['long'], data['lat'], data['long'])

        value = self.p.query(bbox=bbox)
        mh = self._compare(value, 'hydroseq', min)

        out = []
        trim = []
        for i in (mh[P]['levelpathi'],
                  *mh[P]['down_levelpaths'].split(',')):

            down = self.p.query(properties=[('levelpathi', int(i)), ])
            out.extend(down['features'])
            m = self._compare(down, 'hydroseq', min)
            trim.append((m[P]['dnlevelpat'], m[P]['dnhydroseq']))

        trim.append((mh[P]['levelpathi'], mh[P]['hydroseq']))

        outm = []
        for seg in out:
            for i in trim:
                if seg[P]['levelpathi'] == i[0] and \
                   seg[P]['hydroseq'] <= i[1]:
                    outm.append(seg)

        value['features'] = outm
        outputs = {
            'id': 'echo',
            'value': value
        }
        return mimetype, outputs

    def _compare(self, fc, prop, dir):
        val = fc['features'][0]
        for f in fc['features']:
            if dir(f[P][prop], val[P][prop]) != val[P][prop]:
                val = f
        return val

    def __repr__(self):
        return '<RiverRunnerProcessor> {}'.format(self.name)

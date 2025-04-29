# =================================================================
#
# Authors: Ben Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Ben Webb
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

import functools
import logging
import os
from pathlib import Path
from rdflib import Graph


LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()

SELECT = 'SELECT ?collection_id ?parameter_name ?odmvariable ?odmvarname'

PREFIXES = '''
PREFIX : <http://lincolninst.edu/cgs/vocabularies/usbr#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX variablename: <http://vocabulary.odm2.org/variablename/>
PREFIX dct: <http://purl.org/dc/terms/>
'''

BINDS = '''
BIND(CONCAT(LCASE(STR(?label)), "-edr") AS ?collection_id)
BIND(REPLACE(STR(?parameter), "^.*[#/]", "") AS ?parameter_name)
'''


@functools.cache
def get_graph() -> Graph:
    GRAPH = os.getenv('PYGEOAPI_ONTOLOGY_GRAPH',
                      THISDIR / 'ontology.ttl')
    return Graph().parse(GRAPH)


def get_mapping(parameter_names: list) -> dict:
    resp = {}

    VALUES = ' '.join([f'<{p}>' if p.startswith('http') else
                       f'variablename:{p}'
                       for p in parameter_names])
    query = f'''
        {PREFIXES}
        {SELECT}
        WHERE {{
            VALUES ?odmvariable {{
                {VALUES}
            }}

            ?collection skos:broader :c_1805cd26 .
            ?collection skos:prefLabel ?label .
            ?parameter skos:broader+ ?collection .
            ?parameter rdf:type skos:Concept .
            ?parameter skos:inScheme ?scheme .
            ?parameter skos:exactMatch ?odmvariable .
            ?odmvariable skos:prefLabel ?odmvarname .

            {BINDS}
        }}
    '''

    for c in get_graph().query(query):
        cid = str(c.collection_id)
        pname = str(c.parameter_name)
        if cid not in resp:
            resp[cid] = {
                pname: {
                    'key': str(c.odmvariable),
                    'title': str(c.odmvarname)
                }
            }
        else:
            resp[cid][pname] = {
                'key': str(c.odmvariable),
                'title': str(c.odmvarname)
            }

    return resp

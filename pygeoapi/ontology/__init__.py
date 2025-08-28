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
from typing import TypedDict


LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()

SELECT = 'SELECT DISTINCT ?collection_id ?parameter_id ?variable_group ?variable_name' # noqa

SKOS_ANYMATCH = '(skos:exactMatch|^skos:exactMatch|skos:broadMatch|^skos:broadMatch)' # noqa

PREFIXES = '''
PREFIX : <http://lincolninst.edu/cgs/vocabularies/usbr#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX variablename: <http://vocabulary.odm2.org/variablename/>
PREFIX dct: <http://purl.org/dc/terms/>
'''


class KeyTitleDict(TypedDict):
    key: str
    title: str


@functools.cache
def get_graph() -> Graph:
    GRAPH = os.getenv('PYGEOAPI_ONTOLOGY_GRAPH',
                      THISDIR / 'ontology.ttl')
    return Graph().parse(GRAPH)


def get_mapping(parameter_names: list
                ) -> dict[str, dict[str, KeyTitleDict]]:
    """
    Query Ontology graph for matching EDR collectionad and parameters
    to create a dictionary mapping from OGC Collection to ODM2
    Vocabulary

    :param parameter_names: `list` of ODM2 parameter shortnames or IRIs

    :returns: `dict` of ontology mapping
    """
    resp = {}
    VALUES = ''
    if parameter_names != ['*']:
        values = ' '.join([f'<{p}>' if p.startswith('http') else
                           f':{p}' if p.startswith('c_') else
                           f'variablename:{p}'.replace(' ', '+')
                           for p in parameter_names])
        VALUES = f'VALUES ?variable_group {{ {values} }}'

    query = f'''
        {PREFIXES}
        {SELECT}
        WHERE {{
            {VALUES}

            ?variable_group (skos:broader*|^skos:broader*) ?variable ;
                             skos:prefLabel ?variable_name .

            ?collection skos:broader :c_1805cd26 ;
                        skos:hiddenLabel ?collection_id .

            ?parameter skos:hiddenLabel ?parameter_id ;
                       skos:broader+ ?collection ;
                       {SKOS_ANYMATCH} ?variable .
        }}
    '''

    try:
        response = get_graph().query(query)
    except Exception:
        LOGGER.error('Unable to parse query')
        LOGGER.error(query)
        return {}

    for c in response:
        cid = str(c.collection_id)
        pname = str(c.parameter_id).replace('+', ' ')
        if cid not in resp:
            resp[cid] = {
                pname: {}
            }

        if pname not in resp[cid]:
            resp[cid][pname] = {}

        resp[cid][pname].update({str(c.variable_group): str(c.variable_name)})

    return resp

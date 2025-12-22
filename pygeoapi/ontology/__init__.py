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

SELECT = 'SELECT DISTINCT ?collection_id ?parameter_id ?concept_name ?concept_group' # noqa

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
                      THISDIR / 'ontology_min.ttl')
    return Graph().parse(GRAPH)


def get_mapping(parameter_names: list = ['*']
                ) -> dict[str, dict[str, KeyTitleDict]]:
    """
    Query Ontology graph for matching EDR collectionad and parameters
    to create a dictionary mapping from OGC Collection to ODM2
    Vocabulary

    :param parameter_names: `list` of ODM2 parameter shortnames or IRIs

    :returns: `dict` of ontology mapping
    """
    resp = {}

    if parameter_names != ['*']:
        values = ' '.join([f'<{p}>'
                           for p in parameter_names
                           if p.startswith('http')])
        value_names = ' '.join([f'"{p}"@en'
                                for p in parameter_names
                                if not p.startswith('http')])

        if values:
            VALUES = f'VALUES ?concept {{ {values} }}'

        elif value_names:
            VALUES = f'VALUES ?concept_name {{ {value_names} }}\n'

    else:
        VALUES = '''
            ?concept skos:topConceptOf :conceptScheme_8257cf0e ;
                     skos:prefLabel ?concept_name .
        '''

    query = f'''
        {PREFIXES}
        {SELECT}
        WHERE {{
            {VALUES}

        ?concept_group skos:inScheme :conceptScheme_8257cf0e ;
                       skos:broader*/skos:prefLabel ?concept_name .

        ?match (skos:exactMatch|^skos:exactMatch) ?concept_group ;
                    skos:broader/skos:hiddenLabel ?collection_id ;
                    skos:hiddenLabel ?parameter_id .
        }}
    '''

    try:
        response = get_graph().query(query)
    except Exception:
        msg = 'Unable to find parameter in ontology mapping'
        LOGGER.warning(msg, exc_info=True)
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

        resp[cid][pname].update({str(c.concept_name): str(c.concept_group)})

    return resp

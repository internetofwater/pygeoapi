
import functools
import logging
from pathlib import Path
from rdflib import Graph


LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()
GRAPH = THISDIR / 'ontology.ttl'

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
BIND(REPLACE(STR(?parameter), "^.*/", "") AS ?parameter_name)
'''


@functools.cache
def get_graph() -> Graph:

    g = Graph()
    g.parse(GRAPH)
    return g


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
    qres = get_graph().query(query)
    for row in qres:
        cid = str(row.collection_id)
        pname = str(row.parameter_name)
        if cid not in resp:
            resp[cid] = {
                pname: {
                    'id': str(row.odmvariable),
                    'name': str(row.odmvarname)
                }
            }

    return resp


if __name__ == '__main__':
    get_mapping(['reservoirStorage'])
else:
    get_graph()

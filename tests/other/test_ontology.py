# =================================================================
#
# Authors: Ben Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2026 Lincoln Institute of Land Policy
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

import pytest
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, SKOS, RDFS

from pygeoapi.ontology import get_mapping, apply_mapping, apply_unit_conversion

# Namespaces
USBR = Namespace("http://lincolninst.edu/cgs/vocabularies/usbr#")
VAR = Namespace("http://vocabulary.odm2.org/variablename/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")


@pytest.fixture
def point_coverage_data():
    return {
        'type': 'Coverage',
        'domain': {
            'type': 'Domain',
            'domainType': 'PointSeries',
            'axes': {
                'x': {'values': [-10.1]},
                'y': {'values': [-40.2]},
                't': {'values': [
                    '2013-01-01', '2013-01-02', '2013-01-03',
                    '2013-01-04', '2013-01-05', '2013-01-06']}
            }
        },
        'parameters': {
            '47': {
                'type': 'Parameter',
                'description': {'en': 'Reservoir Storage'},
                'unit': {'symbol': 'ac-ft'},
                'observedProperty': {
                    'label': {'en': 'Reservor Storage'}
                }
            }
        },
        'ranges': {
            '47': {
                'axisNames': ['t'],
                'shape': [6],
                'values': [
                    43.9599, 43.9599, 43.9640, 43.9640, 43.9679, 43.987
                ]
            }
        }
    }


@pytest.fixture(autouse=True)
def cache_clear():
    from pygeoapi.ontology import _get_mapping, get_graph
    _get_mapping.cache_clear()
    get_graph.cache_clear()


@pytest.fixture
def ontology_file(tmp_path):
    ttl_path = tmp_path / "ontology.ttl"

    g = Graph()
    g.bind("skos", SKOS)
    g.bind("", USBR)
    g.bind("variablename", VAR)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)

    # Concept scheme
    scheme = USBR["conceptScheme_8257cf0e"]

    # Collection hierarchy
    parent = USBR["c_1805cd26"]
    collection = USBR["rise"]
    param = USBR["47"]
    odmvar = VAR["reservoirStorage"]

    # Parent concept
    g.add((parent, RDF.type, SKOS.Concept))
    g.add((parent, SKOS.inScheme, scheme))

    # Collection concept
    g.add((collection, RDF.type, SKOS.Concept))
    g.add((collection, SKOS.broader, parent))
    g.add((collection, SKOS.prefLabel, Literal("Rise")))
    g.add((collection, SKOS.hiddenLabel, Literal("rise-edr")))
    g.add((collection, SKOS.inScheme, scheme))

    # Parameter concept
    g.add((param, RDF.type, SKOS.Concept))
    g.add((param, SKOS.broader, collection))
    g.add((param, SKOS.inScheme, scheme))
    g.add((param, SKOS.exactMatch, odmvar))
    g.add((param, SKOS.hiddenLabel, Literal("47")))

    # ODM2 variable (concept_group)
    g.add((odmvar, RDF.type, SKOS.Concept))
    g.add((odmvar, SKOS.prefLabel, Literal("Storage", lang="en")))
    g.add((odmvar, SKOS.inScheme, scheme))
    g.add((odmvar, QUDT.hasUnit, UNIT['AC-FT']))

    # QUDT Unit
    g.add((UNIT['AC-FT'], QUDT.symbol, Literal('acre·ft')))
    g.add((UNIT['AC-FT'], RDFS.label, Literal("Acre Foot", lang="en")))

    g.serialize(destination=ttl_path, format="turtle")
    return ttl_path


def test_env_mapping(monkeypatch, ontology_file):
    monkeypatch.setenv("PYGEOAPI_ONTOLOGY_GRAPH", str(ontology_file))
    result = get_mapping(['Storage'])

    assert 'rise-edr' in result
    assert '47' in result['rise-edr']

    mapping = result['rise-edr']['47']
    assert mapping['Storage'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'

    assert len(result['rise-edr']) == 1

    assert 'usace-edr' not in result


def test_get_mapping():
    result = get_mapping(['Storage'])

    assert 'rise-edr' in result
    assert '3' in result['rise-edr']

    mapping = result['rise-edr']['3']
    assert mapping['Storage'] == \
        'http://lincolninst.edu/cgs/vocabularies/usbr#c_c678a27e'

    assert len(result['rise-edr']) == 2

    assert 'usace-edr' in result
    assert 'Percent Conservation Pool' in result['usace-edr']

    mapping = result['usace-edr']['Percent Conservation Pool']
    assert mapping['Storage'] == \
        'http://lincolninst.edu/cgs/vocabularies/usbr#c_6abf9ead'

    assert len(result['usace-edr']) == 2


def test_url_mapping():
    result = get_mapping(
        ['Storage']
    )

    assert 'rise-edr' in result
    assert '3' in result['rise-edr']

    mapping = result['rise-edr']['3']
    assert mapping['Storage'] == \
        'http://lincolninst.edu/cgs/vocabularies/usbr#c_c678a27e'

    assert len(result['rise-edr']) == 2

    assert 'usace-edr' in result
    assert 'Percent Conservation Pool' in result['usace-edr']

    mapping = result['usace-edr']['Percent Conservation Pool']
    assert mapping['Storage'] == \
        'http://lincolninst.edu/cgs/vocabularies/usbr#c_6abf9ead'

    assert len(result['usace-edr']) == 2


def test_empty_mapping():
    result = get_mapping(['notReservoirStorage'])
    assert result == {}


def test_multiple_mappings():
    result = get_mapping(['Storage', 'Inflow'])

    assert 'rise-edr' in result
    assert '3' in result['rise-edr']

    mapping = result['rise-edr']['3']
    assert mapping['Storage'] == \
        'http://lincolninst.edu/cgs/vocabularies/usbr#c_c678a27e'

def test_apply_mapping(monkeypatch, ontology_file, point_coverage_data):
    monkeypatch.setenv("PYGEOAPI_ONTOLOGY_GRAPH", str(ontology_file))

    parameter_groups = {}
    onto_mapping = get_mapping(['Storage', 'Inflow'])
    parameters = point_coverage_data['parameters']
    for parameter in parameters:
        apply_mapping(
            parameters=point_coverage_data['parameters'],
            onto_mapping=onto_mapping,
            parameter_groups=parameter_groups,
            dataset='rise-edr',
            parameter=parameter,
            single_dataset=True
        )

    assert 'Storage' in parameter_groups
    storage = parameter_groups['Storage']
    assert storage['members'] == ['47']

    assert parameters['47']['narrowerThan'] == ['Storage']
    assert parameters['47']['unit']['definition'] == 'http://qudt.org/vocab/unit/AC-FT'

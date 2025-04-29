
import pytest
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, SKOS
from pygeoapi.ontology import get_mapping, get_graph

# Namespaces
USBR = Namespace("http://lincolninst.edu/cgs/vocabularies/usbr#")
VAR = Namespace("http://vocabulary.odm2.org/variablename/")


@pytest.fixture
def ontology_file(tmp_path):
    ttl_path = tmp_path / "ontology.ttl"

    g = Graph()
    g.bind("skos", SKOS)
    g.bind("", USBR)
    g.bind("variablename", VAR)

    # Collection hierarchy
    parent = USBR["c_1805cd26"]
    collection = USBR["rise"]
    param = USBR["47"]
    odmvar = VAR["reservoirStorage"]

    g.add((parent, RDF.type, SKOS.Concept))
    g.add((collection, SKOS.broader, parent))
    g.add((collection, SKOS.prefLabel, Literal("Rise")))

    g.add((param, SKOS.broader, collection))
    g.add((param, RDF.type, SKOS.Concept))
    g.add((param, SKOS.inScheme, URIRef("http://example.org/scheme")))
    g.add((param, SKOS.exactMatch, odmvar))

    g.add((odmvar, SKOS.prefLabel, Literal("Reservoir storage")))

    g.serialize(destination=ttl_path, format="turtle")
    return ttl_path


def test_env_mapping(monkeypatch, ontology_file):
    monkeypatch.setenv("PYGEOAPI_ONTOLOGY_GRAPH", str(ontology_file))
    get_graph.cache_clear()
    result = get_mapping(['reservoirStorage'])

    assert 'rise-edr' in result
    assert '47' in result['rise-edr']

    mapping = result['rise-edr']['47']
    assert mapping['key'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'
    assert mapping['title'] == 'Reservoir storage'

    assert len(result['rise-edr']) == 1

    assert 'usace-edr' not in result


def test_get_mapping():
    get_graph.cache_clear()
    result = get_mapping(['reservoirStorage'])

    assert 'rise-edr' in result
    assert '47' in result['rise-edr']

    mapping = result['rise-edr']['47']
    assert mapping['key'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'
    assert mapping['title'] == 'Reservoir storage'

    assert len(result['rise-edr']) == 3

    assert 'usace-edr' in result
    assert 'Conservation+Storage' in result['usace-edr']

    mapping = result['usace-edr']['Conservation+Storage']
    assert mapping['key'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'
    assert mapping['title'] == 'Reservoir storage'

    assert len(result['usace-edr']) == 1


def test_url_mapping():
    get_graph.cache_clear()
    result = get_mapping(
        ['http://vocabulary.odm2.org/variablename/reservoirStorage']
    )

    assert 'rise-edr' in result
    assert '47' in result['rise-edr']

    mapping = result['rise-edr']['47']
    assert mapping['key'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'
    assert mapping['title'] == 'Reservoir storage'

    assert len(result['rise-edr']) == 3

    assert 'usace-edr' in result
    assert 'Conservation+Storage' in result['usace-edr']

    mapping = result['usace-edr']['Conservation+Storage']
    assert mapping['key'] == \
        'http://vocabulary.odm2.org/variablename/reservoirStorage'
    assert mapping['title'] == 'Reservoir storage'

    assert len(result['usace-edr']) == 1


def test_empty_mapping():
    get_graph.cache_clear()
    result = get_mapping(['notReservoirStorage'])
    assert result == {}

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

import functools
import logging
import os
from pathlib import Path
from rdflib import Graph
from typing import TypedDict

LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()

SELECT = (
    'SELECT DISTINCT ?collection_id ?parameter_id ?concept_name ?concept_group'  # noqa
)

SKOS_ANYMATCH = (
    '(skos:exactMatch|^skos:exactMatch|skos:broadMatch|^skos:broadMatch)'  # noqa
)

DEFAULT_PREFIX = os.getenv(
    'PYGEOAPI_ONTOLOGY_DEFAULT_PREFIX',
    'http://lincolninst.edu/cgs/vocabularies/usbr#'
)

PREFIXES = f"""
PREFIX : <{DEFAULT_PREFIX}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX variablename: <http://vocabulary.odm2.org/variablename/>
PREFIX dct: <http://purl.org/dc/terms/>
"""


CONCEPT_SCHEME = os.getenv(
    'PYGEOAPI_ONTOLOGY_CONCEPT_SCHEME',
    ':conceptScheme_8257cf0e'
)


class KeyTitleDict(TypedDict):
    key: str
    title: str


@functools.cache
def get_graph() -> Graph:
    GRAPH = os.getenv('PYGEOAPI_ONTOLOGY_GRAPH', THISDIR / 'ontology_min.ttl')
    if Path(GRAPH).exists():
        return Graph().parse(GRAPH)


def get_mapping(
    parameter_names: str | list = None,
) -> dict[str, dict[str, KeyTitleDict]]:
    """
    Query Ontology graph for matching EDR collection and parameters
    to create a dictionary mapping from OGC Collection to ODM2
    Vocabulary

    :param parameter_names: `tuple` of ODM2 parameter shortnames or IRIs

    :returns: `dict` of ontology mapping
    """
    if get_graph() is None:
        LOGGER.error('No ontology graph available')
        return {}

    if not parameter_names:
        parameter_names = ['*']

    if isinstance(parameter_names, str):
        parameter_names = parameter_names.split(',')

    try:
        parameter_names = tuple(parameter_names)
        return _get_mapping(parameter_names)
    except Exception as err:
        LOGGER.error(err)
        msg = 'Unable to get ontology mapping'
        LOGGER.error(msg, exc_info=True)
        return {}


@functools.cache
def _get_mapping(
    parameter_names: tuple
) -> dict[str, dict[str, KeyTitleDict]]:
    """
    Inner cacheable function to query Ontology graph
    """

    VALUES = f"""
        ?concept skos:topConceptOf {CONCEPT_SCHEME};
                 skos:prefLabel ?concept_name .
    """

    if '*' not in parameter_names:
        values = ' '.join(
            [f'<{p}>' for p in parameter_names if p.startswith('http')]
        )
        value_names = ' '.join(
            [f'"{p}"@en' for p in parameter_names if not p.startswith('http')]
        )

        if values:
            VALUES = f'VALUES ?concept {{ {values} }}'

        elif value_names:
            VALUES = f'VALUES ?concept_name {{ {value_names} }}\n'

    query = f"""
        {PREFIXES}
        {SELECT}
        WHERE {{
            {VALUES}

        ?concept_group skos:inScheme {CONCEPT_SCHEME} ;
                       skos:broader*/skos:prefLabel ?concept_name .

        ?match (skos:exactMatch|^skos:exactMatch) ?concept_group ;
                    skos:broader/skos:hiddenLabel ?collection_id ;
                    skos:hiddenLabel ?parameter_id .
        }}
    """
    try:
        response = get_graph().query(query)
    except Exception:
        msg = 'Unable to find parameter in ontology mapping'
        LOGGER.warning(msg, exc_info=True)
        return {}

    mapping_dict: dict[str, dict[str, KeyTitleDict]] = {}
    for row in response:

        collection_id = row.collection_id.toPython()
        parameter_id = row.parameter_id.toPython().replace('+', ' ')
        concept_name = row.concept_name.toPython()
        concept_group = row.concept_group.toPython()

        (
            mapping_dict
            .setdefault(collection_id, {})
            .setdefault(parameter_id, {})
            .update({concept_name: concept_group})
        )

    return mapping_dict


def apply_mapping(
    parameters: dict | list,
    onto_mapping: dict[str, dict[str, KeyTitleDict]],
    parameter_groups: dict,
    dataset: str,
    parameter: str,
    single_dataset: bool = False,
):
    """
    Apply ontology mapping to parameter and parameter groups in place

    :param parameters: `dict` or `list` of parameter objects
    :param onto_mapping: ontology mapping dictionary
    :param parameter_groups: parameter groups dictionary to use
    :param dataset: collection identifier
    :param parameter: parameter identifier
    :param single_dataset: whether single dataset is being processed

    :returns: None
    """
    if dataset not in onto_mapping:
        LOGGER.debug(f'No mapping found for {dataset}')
        return

    if isinstance(parameters, list):
        parameter = parameters.index(parameter)

    if parameter not in onto_mapping[dataset]:
        parameters.pop(parameter)
        return

    param_mapping = onto_mapping[dataset][parameter]
    parameters[parameter]['narrowerThan'] = [*param_mapping]
    for param, id in param_mapping.items():
        if param not in parameter_groups:
            parameter_groups[param] = {
                'type': 'ParameterGroup',
                'id': id,
                'label': param,
                # this name key is a holdout for compatibility reasons
                # it can eventually be removed once the frontend no longer
                # depends on it
                'name': param,
                'observedProperty': {
                    'id': param,
                    'label': {'en': param}
                },
                'members': [] if single_dataset else {}
            }

        members = parameter_groups[param]['members']
        if single_dataset:
            members.append(parameter)
        else:
            members.setdefault(dataset, []).append(parameter)


def get_oas_parameter(dataset: str | None = None):
    """
    Get OpenAPI parameter definition for parameter-name query parameter

    :param dataset: collection identifier
    """
    from pygeoapi.openapi import OPENAPI_YAML

    onto_mapping = get_mapping()
    parameters2 = set()

    for collection in onto_mapping:

        if dataset and collection != dataset:
            continue

        parameters = list(
            {next(iter(k))for k in onto_mapping[collection].values()}
        )
        parameters2.update(parameters)

    if len(parameters2) == 0:
        return {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/parameter-name.yaml"}  # noqa
    else:
        return {
            'name': 'parameter-name',
            'in': 'query',
            'schema': {
                'allOf': [
                    {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/parameter-name.yaml"}, # noqa
                    {
                        'type': 'string',
                        'enum': list(parameters2)
                    }
                ]
            }
        }

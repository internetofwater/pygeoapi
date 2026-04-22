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

from copy import deepcopy
import functools
import logging
import os
from pathlib import Path
from rdflib import Graph
from typing import Any, TypedDict

LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()

SELECT = (
    'SELECT DISTINCT ?collection_id ?parameter_id ?parameter_name '
    '?parameter_def ?concept_name ?concept_group'
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
    else:
        raise FileNotFoundError(f"Ontology graph not found at {GRAPH}")


def get_mapping(
    parameter_names: str | list | None = None,
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
            VALUES = f'''
                VALUES ?concept {{ {values} }}
                ?concept skos:broader+/skos:prefLabel ?concept_name .
                '''

        elif value_names:
            VALUES = f'VALUES ?concept_name {{ {value_names} }}\n'

    query = f"""
        {PREFIXES}
        {SELECT}
        WHERE {{
        {VALUES}

        ?concept_group skos:inScheme {CONCEPT_SCHEME} ;
            skos:broader*/skos:prefLabel ?concept_name .

        OPTIONAL {{
            ?concept_group skos:prefLabel ?parameter_name .
        }}
        OPTIONAL {{
            ?concept_group skos:definition ?parameter_def .
        }}

        ?match {SKOS_ANYMATCH} ?concept_group ;
            skos:broader/skos:hiddenLabel ?collection_id ;
            skos:hiddenLabel ?parameter_id .
        }}
    """
    try:
        # rdflib does not type properly, thus
        # it must be simply declared as Any
        response: Any = get_graph().query(query)
    except Exception:
        msg = 'Unable to find parameter in ontology mapping'
        LOGGER.warning(msg, exc_info=True)
        return {}

    mapping_dict: dict[str, dict[str, KeyTitleDict]] = {}
    for row in response:
        collection_id = row.collection_id.toPython()
        parameter_id = row.parameter_id.toPython().replace('+', ' ')
        parameter_name = str(row.parameter_name or '')
        parameter_def = str(row.parameter_def or '')
        concept_name = row.concept_name.toPython()
        concept_group = row.concept_group.toPython()

        (
            mapping_dict
            .setdefault(collection_id, {})
            .setdefault(parameter_id, {})
            .update({
                concept_name: concept_group,
                'parameter_name': parameter_name,
                'parameter_def': parameter_def
            })
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
    # Check if dataset (collection) has is in the ontology mapping
    # if not, then filter out this collection. Should only apply to
    # `/collections` and `/collections/{collection_id}` queries
    if dataset not in onto_mapping:
        LOGGER.debug(f'No mapping found for {dataset}')
        return

    # Check if parameter is in the ontology mapping for dataset (collection)
    # if not, then filter out this parameter. Should only apply to
    # `/collections` and `/collections/{collection_id}` queries
    if parameter not in onto_mapping[dataset]:
        LOGGER.debug(f'No mapping found for {parameter} in {dataset}')
        parameters.pop(parameter)
        return

    # Handle edge case lookup where parameter object is a list
    # instead of an object with key lookup. This is the case
    # for EDR GeoJSON for some reason
    if isinstance(parameters, list):
        parameter = parameters.index(parameter)

    # Get ontology mapping for this dataset and parameter
    param_mapping = deepcopy(onto_mapping[dataset][parameter])

    # Fetch the parameter name and definition from the mapping, if available
    # and apply them to the parameter's name and observedProperty description.
    # This allows us to provide more user-friendly labels and descriptions for
    # parameters based on the Vocbench concept mapping
    param_name = param_mapping.pop('parameter_name', None)
    obs_prop = parameters[parameter]['observedProperty']
    if param_name:
        obs_prop['label'] = {'en': param_name}

    param_def = param_mapping.pop('parameter_def', None)
    if param_def:
        obs_prop['description'] = {'en': param_def}

    # Remaining items are groups that the parameter is mapped to
    # which mean we need to add the parameter to the corresponding group

    # Map parameter to parameterGroup
    parameters[parameter]['narrowerThan'] = [*param_mapping]

    # Map parameter group to parameters
    for param, id in param_mapping.items():

        # Create parameter groups for each concept
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

        # Add parameter to parameter group members. If single_dataset
        # is True, we do not need to namespace members by dataset.
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

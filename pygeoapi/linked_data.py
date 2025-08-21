# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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

""" Linked data capabilities
Returns content as linked data representations
"""

import logging
from typing import Callable

from pygeoapi.util import is_url, render_j2_template, url_join
from pygeoapi import l10n
from shapely.geometry import shape
from shapely.ops import unary_union

LOGGER = logging.getLogger(__name__)


def jsonldify(func: Callable) -> Callable:
    """
    Decorator that transforms app configuration\
    to include a JSON-LD representation

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args, **kwargs):
        apireq = args[1]
        format_ = getattr(apireq, 'format')
        if not format_ == 'jsonld':
            return func(*args, **kwargs)
        # Function args have been pre-processed, so get locale from APIRequest
        locale_ = getattr(apireq, 'locale')
        LOGGER.debug('Creating JSON-LD representation')
        cls = args[0]
        cfg = cls.config
        meta = cfg.get('metadata', {})
        contact = meta.get('contact', {})
        provider = meta.get('provider', {})
        ident = meta.get('identification', {})
        fcmld = {
          "@context": {
              "skos": "http://www.w3.org/2004/02/skos/core#",
              "dataset": "@graph",
              "@language": locale_
          },
          "@type": "skos:ConceptScheme",
          "@id": cfg.get('server', {}).get('url'),
          "skos:prefLabel": l10n.translate(ident.get('title'), locale_),
          "skos:narrower":{
            "@type": "skos:Concept",
            "@id": f"{cls.base_url}/collections",
            "skos:topConceptOf": {"@id": cls.base_url},
            "skos:prefLabel": "Collections"
          }
        }
        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner


def jsonldify_collection(cls, collection: dict, locale_: str) -> dict:
    """
    Transforms collection into a JSON-LD representation

    :param cls: API object
    :param collection: `collection` as prepared for non-LD JSON
                       representation
    :param locale_: The locale to use for translations (if supported)

    :returns: `collection` a dictionary, mapped into JSON-LD, of
              type schema:Dataset
    """
    uri = f"{cls.base_url}/collections/{collection['id']}"
    dataset = {
        "@id": uri,
        "@type": "skos:Concept",
        "skos:prefLabel": l10n.translate(collection['title'], locale_),
        "skos:hiddenLabel": collection['id'],
        "skos:inScheme": {"@id": cls.base_url},
        "skos:broader": {"@id": f"{cls.base_url}/collections"},
        "skos:note": l10n.translate(collection['description'], locale_),
        "@graph": []
    }

    parameters = collection.get('parameter_names', {})
    for parameter, values in parameters.items():
        dataset["@graph"].append({
            "@id": f"{uri}/parameters/{parameter}",
            "@type": "skos:Concept",
            "skos:prefLabel": values['name'],
            "skos:hiddenLabel": parameter,
            "skos:broader": {"@id": uri},
            "skos:inScheme": {"@id": cls.base_url},
            "qudt:hasUnit": {"@id": values['unit']['symbol']['type'] + values['unit']['symbol']['value']}
        })

    return dataset


def geojson2jsonld(cls, data: dict, dataset: str,
                   identifier: str = None, id_field: str = 'id') -> str:
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param cls: API object
    :param data: dict of data:
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)
    :param id_field: item identifier_field (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """

    LOGGER.debug('Fetching context from resource configuration')
    context = cls.config['resources'][dataset].get('context', []).copy()
    templates = cls.get_dataset_templates(dataset)

    defaultVocabulary = {
        'schema': 'https://schema.org/',
        'gsp': 'http://www.opengis.net/ont/geosparql#',
        'type': '@type'
    }

    if identifier:
        # Expand properties block
        data.update(data.pop('properties'))

        # Include multiple geometry encodings
        if (data.get('geometry') is not None):
            jsonldify_geometry(data)

        data['@id'] = identifier

    else:
        # Collection of jsonld
        defaultVocabulary.update({
            'features': 'schema:itemListElement',
            'FeatureCollection': 'schema:itemList'
        })

        ds_url = url_join(cls.get_collections_url(), dataset)
        data['@id'] = ds_url

        for i, feature in enumerate(data['features']):
            # Get URI for each feature
            identifier_ = feature.get(id_field,
                                      feature['properties'].get(id_field, ''))
            if not is_url(str(identifier_)):
                identifier_ = f"{ds_url}/items/{feature['id']}"  # noqa

            # Include multiple geometry encodings
            if feature.get('geometry') is not None:
                jsonldify_geometry(feature)

            data['features'][i] = {
                '@id': identifier_,
                'type': 'schema:Place',
                **feature.pop('properties'),
                **feature
            }

    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')

    data['links'] = data.pop('links')

    ldjsonData = {
        '@context': [defaultVocabulary, *(context or [])],
        **data
    }

    if identifier:
        # Render jsonld template for single item
        LOGGER.debug('Rendering JSON-LD item template')
        content = render_j2_template(
            cls.tpl_config, templates,
            'collections/items/item.jsonld', ldjsonData)

    else:
        # Render jsonld template for /items
        LOGGER.debug('Rendering JSON-LD items template')
        content = render_j2_template(
            cls.tpl_config, templates,
            'collections/items/index.jsonld', ldjsonData)

    return content


def jsonldify_geometry(feature: dict) -> None:
    """
    Render JSON-LD for feature with GeoJSON, Geosparql/WKT, and
    schema geometry encodings.

    :param feature: feature body to with GeoJSON geometry

    :returns: None
    """

    feature['type'] = 'schema:Place'

    geo = feature.get('geometry')
    geom = shape(geo)

    # GeoJSON geometry
    feature['geometry'] = feature.pop('geometry')

    # Geosparql geometry
    feature['gsp:hasGeometry'] = {
        '@type': f'http://www.opengis.net/ont/sf#{geom.geom_type}',
        'gsp:asWKT': {
            '@type': 'http://www.opengis.net/ont/geosparql#wktLiteral',
            '@value': f'{geom.wkt}'
        }
    }

    # Schema geometry
    try:
        feature['schema:geo'] = geom2schemageo(geom)
    except AttributeError:
        msg = f'Unable to parse schema geometry for {feature["id"]}'
        LOGGER.warning(msg)


def geom2schemageo(geom: shape) -> dict:
    """
    Render Schema Geometry from a GeoJSON base.

    :param geom: shapely geom of feature

    :returns: dict of rendered schema:geo geometry
    """
    f = {'@type': 'schema:GeoShape'}
    if geom.geom_type == 'Point':
        return {
            '@type': 'schema:GeoCoordinates',
            'schema:longitude': geom.x,
            'schema:latitude': geom.y
        }

    elif geom.geom_type == 'LineString':
        points = [f'{x},{y}' for (x, y, *_) in geom.coords[:]]
        f['schema:line'] = ' '.join(points)
        return f

    elif geom.geom_type == 'MultiLineString':
        points = list()
        for line in geom.geoms:
            points.extend([f'{x},{y}' for (x, y, *_) in line.coords[:]])
        f['schema:line'] = ' '.join(points)
        return f

    elif geom.geom_type == 'MultiPoint':
        points = [(x, y) for pt in geom.geoms for (x, y, *_) in pt.coords]
        points.append(points[0])

    elif geom.geom_type == 'Polygon':
        points = geom.exterior.coords[:]

    elif geom.geom_type == 'MultiPolygon':
        # MultiPolygon to Polygon (buffer of 0 helps ensure manifold polygon)
        poly = unary_union(geom.buffer(0))
        if poly.geom_type.startswith('Multi') or not poly.is_valid:
            LOGGER.debug(f'Invalid MultiPolygon: {poly.geom_type}')
            poly = poly.convex_hull
            LOGGER.debug(f'New MultiPolygon: {poly.geom_type}')
        points = poly.exterior.coords[:]

    else:
        points = list()
        for p in geom.geoms:
            try:
                points.extend(p.coords[:])
            except NotImplementedError:
                points.extend(p.exterior.coords[:])

    schema_polygon = [f'{x},{y}' for (x, y, *_) in points]

    f['schema:polygon'] = ' '.join(schema_polygon)

    return f

# =================================================================
#
# Authors: Ben Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Lincoln Institute of Land Policy
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

import geopandas as gpd
import os
import tempfile
import zipfile
import io
import logging

from pygeoapi.formatter.base import BaseFormatter

LOGGER = logging.getLogger(__name__)


class ShapefileFormatter(BaseFormatter):
    """Shapefile formatter"""

    def __init__(self, formatter_def: dict):
        """
        Initialize object

        :param formatter_def: formatter definition

        :returns: `pygeoapi.formatter.shape.ShapefileFormatter`
        """

        super().__init__({'name': 'shp'})
        self.mimetype = 'application/zip; charset=utf-8'
        self.filename = formatter_def.get('filename', 'data')

    def write(self, options: dict = {}, data: dict = None) -> str:
        """
        Generate data in Zipped Shapefile format

        :param options: Shapefile formatting options
        :param data: dict of GeoJSON data

        :returns: string representation of format
        """

        gdf = gpd.GeoDataFrame.from_features(data['features'])
        gdf.set_crs('EPSG:4326', inplace=True)

        # Create a temporary directory for shapefile components
        with tempfile.TemporaryDirectory() as tmpdir:
            shapefile_path = os.path.join(tmpdir, f'{self.filename}.shp')
            gdf.to_file(shapefile_path)

            # Create a zip in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(
                zip_buffer, 'w', zipfile.ZIP_DEFLATED
            ) as zipf:
                for filename in os.listdir(tmpdir):
                    full_path = os.path.join(tmpdir, filename)
                    zipf.write(full_path, arcname=filename)

            return zip_buffer.getvalue()

    def __repr__(self):
        return f'<KMLFormatter> {self.name}'


class KMLFormatter(BaseFormatter):
    """KML formatter"""

    def __init__(self, formatter_def: dict):
        """
        Initialize object

        :param formatter_def: formatter definition

        :returns: `pygeoapi.formatter.shape.KMLFormatter`
        """

        super().__init__({'name': 'kml'})
        self.mimetype = 'application/vnd.google-earth.kml+xml'
        self.filename = formatter_def.get('filename', 'data')

    def write(self, options: dict = {}, data: dict = None) -> str:
        """
        Generate data in KML format

        :param options: KML formatting options
        :param data: dict of GeoJSON data

        :returns: string representation of format
        """

        gdf = gpd.GeoDataFrame.from_features(data['features'])
        gdf.set_crs('EPSG:4326', inplace=True)

        output = io.BytesIO()
        gdf.to_file(output, driver='KML')

        return output.getvalue()

    def __repr__(self):
        return f'<KMLFormatter> {self.name}'

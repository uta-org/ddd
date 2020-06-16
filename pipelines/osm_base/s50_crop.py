# ddd - DDD123
# Library for procedural scene modelling.
# Jose Juan Montes 2020

import sys

import pyproj

from ddd.ddd import ddd
from ddd.geo import terrain
from ddd.osm import osm
from ddd.osm.osm import project_coordinates
from ddd.pipeline.decorators import dddtask

"""
"""


@dddtask(order="50.80.10.+", log=True)
def osm_crop(pipeline, osm, root, logger):
    """Crops features in different ways."""
    pass

@dddtask(path="/Areas/*")
def osm_crop_areas(obj, osm, root, logger):
    obj.extra['ddd:crop'] = 'area'

@dddtask(path="/Ways/*")
def osm_crop_ways(obj, osm, root, logger):
    obj.extra['ddd:crop'] = 'area'

@dddtask(path="/Items/*")
def osm_crop_items(obj, osm, root, logger):
    obj.extra['ddd:crop'] = 'centroid'

@dddtask(path="/Buildings/*")
def osm_crop_buidings(obj, osm, root, logger):
    obj.extra['ddd:crop'] = 'centroid'


@dddtask(order="50.80.90.+", log=True)
def osm_crop_apply(obj, osm, root, logger):
    pass

@dddtask(select='["ddd:crop" = "area"]')
def osm_crop_apply_area(obj, osm, root, logger):
    obj = obj.intersection(osm.area_crop2)
    return obj

@dddtask(select='["ddd:crop" = "centroid"]')
def osm_crop_apply_centroid(obj, osm, root, logger):
    point = obj.centroid()
    contained = osm.area_crop2.contains(point)
    if not contained: return False



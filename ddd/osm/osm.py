# ddd - D1D2D3
# Library for simple scene modelling.
# Jose Juan Montes 2020

from collections import defaultdict, namedtuple
import logging
import math
import random
import sys

from csg import geom as csggeom 
from csg.core import CSG
import geojson
import noise
import pyproj
from shapely import geometry
from shapely.geometry import shape
from shapely.geometry.geo import shape
from shapely.ops import transform

from ddd.ddd import DDDObject2, DDDObject3
from ddd.ddd import ddd
from ddd.pack.sketchy import terrain, plants, urban
from trimesh import creation, primitives, boolean
import trimesh
from trimesh.base import Trimesh
from trimesh.path import segments
from trimesh.path.path import Path
from trimesh.scene.scene import Scene, append_scenes 
from trimesh.visual.material import SimpleMaterial 
from shapely.geometry.linestring import LineString
from ddd.osm.buildings import BuildingOSMBuilder
from ddd.osm.ways import WaysOSMBuilder
from ddd.osm.areas import AreasOSMBuilder
from ddd.osm.items import ItemsOSMBuilder


# Get instance of logger for this module
logger = logging.getLogger(__name__)

WayConnection = namedtuple("WayConnection", "other self_idx other_idx") 

def project_coordinates(coords, transformer):
    if isinstance(coords[0], list):
        coords = [project_coordinates(c, transformer) for c in coords]
    elif isinstance(coords[0], float):
        x, y = transformer.transform(coords[0], coords[1])
        coords = [x, y]
        #c = _c(coords)
    else:
        raise AssertionError()
    
    return coords

class OSMBuilder():

    mat_highlight = ddd.material(color='#ff00ff')
    
    mat_lane = ddd.material(color='#1db345')
    mat_terrain = ddd.material(color='#e6821e')
    mat_border = ddd.material(color='#f0f0ff')
    
    mat_asphalt = ddd.material(color='#202020')
    mat_dirt = ddd.material(color="#b58800")
    mat_railway = ddd.material(color="#47443e")
    mat_sidewalk = ddd.material(color='#e0d0d0')
    mat_pavement = ddd.material(color='#c0c0b0')
    mat_pathwalk = ddd.material(color='#78281e')
    mat_park = ddd.material(color='#1db345')
    mat_pitch = ddd.material(color='#196118')
    mat_sea = ddd.material(color='#3d43b5')
    
    mat_bronze = ddd.material(color='#f0cb11')
    mat_steel = ddd.material(color='#78839c')
    
    mat_building_1 = ddd.material(color='#f7f0be')
    mat_building_2 = ddd.material(color='#bdb9a0')
    mat_building_3 = ddd.material(color='#c49156')
    mat_roof_tile = ddd.material(color='#f25129') 

    def __init__(self, features=None, area=None, osm_proj=None, ddd_proj=None, config=None):
        
        self.items = ItemsOSMBuilder(self)
        self.ways = WaysOSMBuilder(self)
        self.areas = AreasOSMBuilder(self)
        self.buildings = BuildingOSMBuilder(self)
        
        self.simplify_tolerance = 0.01
        
        self.layer_indexes = ('-2', '-1', '0', '1', '2', '-2a', '-1a', '0a', '1a')
        
        self.layer_heights = {'-2': -12.0, 
                              '-1': -5.0, 
                              '0': 0.0, 
                              '1': 6.0, 
                              '2': 12.0, 
                              #'-2a': -9.0, '-1a': -2.5, '0a': 3.0, '1a': 9.0}
                              #'-2a': -12.0, '-1a': -5.0, '0a': 0.0, '1a': 6.0}
                              '-2a': 0.0, '-1a': 0.0, '0a': 0.0, '1a': 0.0}

        
        self.features = features if features else []
        self.area = area  # Polygon or shape for initial selectionof features (ie: city)
        self.area_crop = ddd.rect([-500, -500, 500, 500]).geom # Square to generate
        #self.area_crop = ddd.rect([-500, -750, 1000, 750]).geom # Square to generate
        
        self.osm_proj = osm_proj
        self.ddd_proj = ddd_proj
        
        self.items_1d = DDDObject2()
        self.items_3d = DDDObject3()
        
        self.ways_1d = None
        self.ways_2d = defaultdict(DDDObject2)
        self.ways_3d = defaultdict(DDDObject3)
        
        self.areas_2d = DDDObject2()
        self.areas_3d = DDDObject3()
        
        self.buildings_2d = None
        self.buildings_3d = None
        
        self.water_3d = DDDObject3()
        self.ground_3d = DDDObject3()
        
        #self.sidewalks_3d_l1 = DDDObject3()
        #self.walls_3d_l1 = DDDObject3()
        #self.floor_3d_l1 = DDDObject3()
        
        
    '''
    # Deprecated, but may be needed (but as preprocessing) if we support attributes without osmimporter in the pipeline
    def other_tags(sfeature):
        other_tags = {}
        other_tags_str = feature['properties'].get('other_tags', None)
        if other_tags_str:
            for t in other_tags_str.split(","):
                try:
                    k, v = t.split("=>")
                    other_tags[k.replace('"', "").strip()] = v.replace('"', "").strip() 
                except:
                    print("Invalid Tag: %s" % t)
        return other_tags
    '''

    def load_geojson(self, files):
        
        features = []
        for f in files:
            fs = geojson.load(open(f, 'r'))
            features.extend(fs['features'])
    
        seen = set()
        dedup = []
        for f in features:
            oid = hash(str(f))  # f['properties']['osm_id']
            if oid not in seen:
                seen.add(oid)
                dedup.append(f)
        
        logger.info("Loaded %d features (%d unique)" % (len(features), len(dedup)))
        features = dedup
                
        # Filter features
        '''
        filtered = []
        for f in features:
            geom = shape(f['geometry'])
            try:
                if self.area.contains(geom):
                    filtered.append(f)
            except Exception as e:
                logger.warn("Ignored geometry: %s" % e)
        features = filtered
        logger.info("Using %d features after filtering" % (len(features)))
        '''
                
        # Project to local
        transformer = pyproj.Transformer.from_proj(self.osm_proj, self.ddd_proj)
        for f in features:
            f['geometry']['coordinates'] = project_coordinates(f['geometry']['coordinates'], transformer)
    
        # Crop
        # FIXME: this shall be done later or twice, to allow for external objects, slice some, etc...
        filtered = []
        for f in features:
            geom = shape(f['geometry'])
            #if self.area_crop.contains(geom.centroid):
            if self.area_crop.intersects(geom):
                filtered.append(f)
        features = filtered
        logger.info("Using %d features after cropping" % (len(features)))
        
        self.features = features

    def preprocess_features(self):
        """
        Corrects inconsistencies and adapts OSM data for generation.
        """
        
        # Correct layers
        for f in self.features:
            if f.properties.get('tunnel', None) == 'yes' and f.properties.get('layer', None) is None:
                f.properties['layer'] = "-1"
            if f.properties.get('layer', None) is None:
                f.properties['layer'] = "0"
        
    def layer_height(self, layer_idx):
        return self.layer_heights[layer_idx]

    def generate(self):

        self.preprocess_features()
        
        # Generate items for point features
        self.items.generate_items_1d()
        
        # Roads sorted + intersections + metadata
        self.ways.generate_ways_1d() 
        self.ways.generate_ways_2d()
        
        #self.roads_2d_lm1 = self.generate_roads_2d(-1)
        #self.roads_2d_l0 = self.generate_roads_2d(0)
        #self.roads_2d_l1 = self.generate_roads_2d(1)
        
        # Regions
        # - fill (order) + correct types if interesect or marker: (park, forest, etc...)
        # - ground (fill rest of space)
        # - holes (for layer beyond)
        
        self.areas.generate_areas_2d()
        self.areas.generate_areas_2d_interways()  # and assign types
        #self.generate_unbounded_squares_2d() # this is current cropped ground, replace with this, assign types
        #self.assign_area_types() #
        
        
        # Buildings
        self.buildings.generate_buildings_2d()
        self.buildings.link_features_2d()
        
        # Associate features (amenities, etc) to 2D objects (buildings, etc)
        #self.buildings.associate_features()
        
        self.areas.generate_coastline_3d(self.area_crop)
        self.areas.generate_ground_3d(self.area_crop) # separate in 2d + 3d, also subdivide (calculation is huge - core dump-)
        
        # 3D Build
        
        # Ways 3D
        self.ways.generate_ways_3d() 
        # Areas 3D
        self.areas.generate_areas_3d()
        # Buildings 3D
        self.buildings.generate_buildings_3d()
        
        # Walls and fences(!) (2D?)

        # Urban decoration (trees, fountains, etc)
        self.items.generate_items_3d()
        
        # Trees, parks, gardens... 

        scene = [self.areas_3d, self.ground_3d, self.water_3d,
                 #self.sidewalks_3d_lm1, self.walls_3d_lm1, self.ceiling_3d_lm1,
                 #self.sidewalks_3d_l1, self.walls_3d_l1, self.floor_3d_l1,
                 self.buildings_3d, self.items_3d]
        
        scene = ddd.group(scene + list(self.ways_3d.values()))
        
        return scene 


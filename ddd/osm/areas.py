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
from numpy import angle
import pyproj
from shapely import geometry
from shapely.errors import TopologicalError
from shapely.geometry import shape
from shapely.geometry.geo import shape
from shapely.geometry.linestring import LineString
from shapely.geometry.polygon import LinearRing
from shapely.ops import transform
from trimesh import creation, primitives, boolean
import trimesh
from trimesh.base import Trimesh
from trimesh.path import segments
from trimesh.path.path import Path
from trimesh.scene.scene import Scene, append_scenes
from trimesh.visual.material import SimpleMaterial

from ddd.ddd import DDDObject2, DDDObject3
from ddd.ddd import ddd
from ddd.pack.sketchy import plants, urban, sports
from ddd.geo import terrain
from ddd.core.exception import DDDException


# Get instance of logger for this module
logger = logging.getLogger(__name__)

class AreasOSMBuilder():

    def __init__(self, osmbuilder):

        self.osm = osmbuilder

    def generate_areas_2d(self):
        logger.warning("BRING AREAITEMS here and sort them too. Possibly remove areaitems, and refactor from here (2D -> shapes).")

        areas = []
        for feature in self.osm.features:
            if feature['geometry']['type'] not in ('Polygon', ):
                continue
            if feature.properties.get('building', None) is not None:
                # FIXME: better filter which features we are interested in
                continue

            area = ddd.shape(feature['geometry'], name="Area: %s" % (feature['properties'].get('name', feature['properties'].get('id'))))

            if not area.geom.is_valid:
                logger.info("Invalid area (discarding): %s", area)
                continue

            area.extra['osm:feature'] = feature
            area.extra['ddd:area:type'] = None
            area.extra['ddd:area:area'] = area.geom.area
            area.extra['ddd:area:container'] = None
            area.extra['ddd:area:contained'] = []
            area.extra['ddd:baseheight'] = 0.0
            areas.append(area)

        logger.info("Sorting 2D areas  (%d).", len(areas))
        areas.sort(key=lambda a: a.extra['ddd:area:area'])

        for idx in range(len(areas)):
            area = areas[idx]
            for larger in areas[idx + 1:]:
                if larger.contains(area):
                    logger.debug("Area %s contains %s.", larger, area)
                    area.extra['ddd:area:container'] = larger
                    larger.extra['ddd:area:contained'].append(area)
                    break

        logger.info("Generating 2D areas (%d)", len(areas))

        # Union all roads in the plane to subtract
        union = ddd.group([self.osm.ways_2d['0'], self.osm.ways_2d['-1a'],
                           self.osm.areas_2d]).union()

        for narea in areas:
        #for feature in self.osm.features:
            feature = narea.extra['osm:feature']

            if feature['geometry']['type'] == 'Point':
                continue

            narea.extra['ddd:area:original'] = narea

            # Subtract areas contained (use contained relationship)
            for contained in narea.extra['ddd:area:contained']:
                narea = narea.subtract(contained)

            area = None
            if feature['properties'].get('leisure', None) in ('park', 'garden'):
                narea = narea.subtract(union)
                area = self.generate_area_2d_park(narea)
            elif feature['properties'].get('landuse', None) in ('grass', ):
                narea = narea.subtract(union)
                area = self.generate_area_2d_park(narea)
            if feature['properties'].get('leisure', None) in ('pitch', ):  # Cancha
                area = self.generate_area_2d_pitch(narea)
            elif feature['properties'].get('landuse', None) in ('railway', ):
                area = self.generate_area_2d_railway(narea)
            elif feature['properties'].get('landuse', None) in ('brownfield', ):
                area = self.generate_area_2d_unused(narea)
                narea = narea.subtract(union)
            elif feature['properties'].get('amenity', None) in ('school', ):
                narea = narea.subtract(union)
                area = self.generate_area_2d_school(narea)

            #elif feature['properties'].get('amenity', None) in ('fountain', ):
            #    area = self.generate_area_2d_school(feature)

            if area:
                logger.debug("Area: %s", area)
                area = area.subtract(union)

                self.osm.areas_2d.append(area)
                #self.osm.areas_2d.children.extend(area.individualize().children)

    def generate_area_2d_park(self, area):

        #area = ddd.shape(feature["geometry"], name="Park: %s" % feature['properties'].get('name', None))
        feature = area.extra['osm:feature']
        area = area.material(ddd.mats.park)
        area.name = "Park: %s" % feature['properties'].get('name', None)
        area.extra['_ddd:area'] = 'park'

        # Add trees if necesary
        # FIXME: should not check for None in intersects, filter shall not return None (empty group)
        trees = self.osm.items_1d.filter(lambda o: o.extra.get('natural') == 'tree')
        has_trees = area.intersects(trees)
        add_trees = not has_trees # and area.geom.area > 100

        if add_trees:
            tree_density_m2 = 0.0025  # decimation would affect after
            num_trees = int((area.geom.area * tree_density_m2))
            if num_trees == 0 and random.uniform(0, 1) < 0.5: num_trees = 1
            num_trees = min(num_trees, 20)
            logger.debug("Adding %d trees to %s", num_trees, area)
            #logger.warning("Should be adding items_1d or items_2d, not 3D directly")
            for p in area.random_points(num_points=num_trees):
                #plant = plants.plant().translate([p[0], p[1], 0.0])
                #self.osm.items_3d.children.append(plant)
                tree = ddd.point(p, name="Tree")
                tree.extra['natural'] = 'tree'
                self.osm.items_1d.children.append(tree)

        return area

    def generate_area_2d_pitch(self, area):
        feature = area.extra['osm:feature']
        area.name = "Pitch: %s" % feature['properties'].get('name', None)
        area.extra['ddd:area:type'] = 'pitch'
        area = area.material(ddd.mats.pitch)
        return area

    def generate_area_2d_railway(self, area):
        feature = area.extra['osm:feature']
        area.name = "Railway area: %s" % feature['properties'].get('name', None)
        area = area.material(ddd.mats.dirt)
        area = self.generate_wallfence_2d(area)
        return area

    def generate_area_2d_school(self, area):
        feature = area.extra['osm:feature']
        area.name = "School: %s" % feature['properties'].get('name', None)
        area = area.material(ddd.mats.dirt)
        area.extra['ddd:height'] = 0.0

        area = self.generate_wallfence_2d(area, doors=2)

        return area

    def generate_area_2d_unused(self, area, wallfence=True):
        feature = area.extra['osm:feature']
        area.name = "Unused land: %s" % feature['properties'].get('name', None)
        area = area.material(ddd.mats.dirt)
        area.extra['ddd:height'] = 0.0

        if wallfence:
            area = self.generate_wallfence_2d(area)
        #if ruins:
        #if construction
        #if ...

        return area

    def generate_wallfence_2d(self, area, fence_ratio=0.0, wall_thick=0.3, doors=1):

        area_original = area.extra['ddd:area:original']
        reduced_area = area_original.buffer(-wall_thick)

        wall = area.subtract(reduced_area).material(ddd.mats.bricks)
        wall = wall.subtract(self.osm.buildings_2d)
        wall.extra['ddd:height'] = 1.8

        #ddd.uv.map_2d_polygon(wall, area.linearize())
        area = ddd.group2([area, wall])

        return area

    def generate_areas_2d_interways(self):

        logger.info("Generating 2D areas between ways")

        #self.osm.ways_2d['0'].dump()
        #self.osm.ways_2d['-1a'].dump()
        #self.osm.areas_2d.dump()
        try:
            union = ddd.group([self.osm.ways_2d['0'], self.osm.ways_2d['-1a'], self.osm.areas_2d]).union()
        except TopologicalError as e:
            logger.error("Error calculating interways: %s", e)
            l0 = self.osm.ways_2d['0'].union()
            lm1a = self.osm.ways_2d['-1a'].union()
            #l0a = self.osm.ways_2d['0a'].union()  # shall be trimmed  # added to avoid height conflicts but leaves holes
            c = self.osm.areas_2d.union()
            try:
                eps = 0.01
                union = ddd.group2([c, l0, lm1a])
                union = union.buffer(eps, 1, join_style=ddd.JOIN_MITRE).buffer(-eps, 1, join_style=ddd.JOIN_MITRE)
                union = union.union()
            except TopologicalError as e:
                logger.error("Error calculating interways (2): %s", e)
                union = ddd.group2()
                #union = ddd.group([self.osm.ways_2d['0'], self.osm.ways_2d['-1a'], self.osm.areas_2d]).union()

        #union = union.buffer(0.5)
        #union = union.buffer(-0.5)
        if not union.geom: return

        for c in ([union.geom] if union.geom.type == "Polygon" else union.geom):
            if c.type == "LineString":
                logger.warning("Interways areas union resulted in LineString geometry. Skipping.")
                continue
            for interior in c.interiors:
                area = ddd.polygon(interior.coords, name="Interways area")
                if area:
                    area = area.subtract(union)
                    area = area.clean(eps=0.01)
                    area = area.material(ddd.mats.pavement)
                    self.osm.areas_2d.children.append(area)
                else:
                    logger.warn("Invalid square.")


    def generate_coastline_3d(self, area_crop):

        logger.info("Generating water and land areas according to coastline: %s", (area_crop.bounds))

        #self.water_3d = terrain.terrain_grid(self.area_crop.bounds, height=0.1, detail=200.0).translate([0, 0, 1]).material(mat_sea)

        water = ddd.rect(area_crop.bounds, name="Ground")
        coastlines = []
        coastlines_1d = []
        for way in self.osm.ways_1d.children:
            if way.extra['natural'] == 'coastline':
                coastlines_1d.append(way)
                coastlines.append(way.buffer(0.1))

        logger.debug("Coastlines: %s", (coastlines_1d, ))
        if not coastlines:
            logger.info("No coastlines in the feature set.")
            return

        coastlines = ddd.group(coastlines)
        coastlines_1d = ddd.group(coastlines_1d)

        coastline_areas = water.subtract(coastlines)
        #coastline_areas.save("/tmp/test.svg")
        #coastline_areas.dump()

        areas = []
        areas_2d = []
        geoms = coastline_areas.geom.geoms if coastline_areas.geom.type == 'MultiPolygon' else [coastline_areas.geom]
        for water_area_geom in geoms:
            # Find closest point, closest segment, and angle to closest segment
            water_area_point = water_area_geom.representative_point()
            p, segment_idx, segment_coords_a, segment_coords_b, closest_obj = coastlines_1d.closest_segment(ddd.shape(water_area_point))
            pol = LinearRing([segment_coords_a, segment_coords_b, water_area_point.coords[0]])

            if not pol.is_ccw:
                area_2d = ddd.shape(water_area_geom)
                #area_3d = area_2d.extrude(-0.2)
                area_3d = area_2d.triangulate()
                area_3d = area_3d.material(ddd.mats.sea)
                area_3d.extra['ddd:collider'] = False
                area_3d.extra['ddd:shadows'] = False
                areas_2d.append(area_2d)
                areas.append(area_3d)

        if areas:
            self.osm.water_3d = ddd.group(areas)
            self.osm.water_2d = ddd.group(areas_2d)
        else:
            logger.debug("No water areas from coastline generated.")

    '''
    def generate_ground_3d_old(self, area_crop):

        logger.info("Generating terrain (bounds: %s)", area_crop.bounds)

        #terr = terrain.terrain_grid(distance=500.0, height=1.0, detail=25.0).translate([0, 0, -0.5]).material(mat_terrain)
        terr = terrain.terrain_geotiff(area_crop.bounds, detail=10.0, ddd_proj=self.osm.ddd_proj).material(ddd.mats.terrain)
        #terr2 = terrain.terrain_grid(distance=60.0, height=10.0, detail=5).translate([0, 0, -20]).material(mat_terrain)

        self.osm.ground_3d = terr
    '''

    def generate_ground_3d(self, area_crop):

        logger.info("Generating terrain (bounds: %s)", area_crop.bounds)

        #terr = terrain.terrain_grid(distance=500.0, height=1.0, detail=25.0).translate([0, 0, -0.5]).material(mat_terrain)
        #terr = terrain.terrain_geotiff(area_crop.bounds, detail=10.0, ddd_proj=self.osm.ddd_proj).material(mat_terrain)
        #terr2 = terrain.terrain_grid(distance=60.0, height=10.0, detail=5).translate([0, 0, -20]).material(mat_terrain)
        #terr = ddd.grid2(area_crop.bounds, detail=10.0).buffer(0.0)  # useless, shapely does not keep triangles when operating
        terr = ddd.rect(area_crop.bounds, name="Ground")

        terr = terr.subtract(self.osm.ways_2d['0'])
        terr = terr.clean(eps=0.01)

        terr = terr.subtract(self.osm.ways_2d['-1a'])
        terr = terr.clean(eps=0.01)

        #terr = terr.subtract(self.osm.ways_2d['0a'])  # added to avoid floor, but shall be done better, by layers spawn and base_height,e tc
        terr = terr.subtract(self.osm.areas_2d)
        terr = terr.clean(eps=0.01)

        terr = terr.subtract(self.osm.water_2d)
        terr = terr.clean(eps=0.01)

        # The buffer is fixing a core segment violation :/
        #terr.save("/tmp/test.svg")
        #terr.dump()
        #terr.show()
        #terr = ddd.group([DDDObject2(geom=s.buffer(0.5).buffer(-0.5)) for s in terr.geom.geoms if not s.is_empty])

        #terr.save("/tmp/test.svg")
        #terr = terr.triangulate()
        logger.warning("There's a buffer(0.000-0.001) operation which shouldn't be here: improve and use 'clean()'.")
        try:
            #terr = terr.individualize()
            #terr.validate()
            terr = terr.buffer(0.001)
            #terr = terr.buffer(0.0)

            #terr = terr.extrude(0.3)
            terr = terr.triangulate()
        except ValueError as e:
            logger.error("Cannot generate terrain (FIXME): %s", e)
            raise
        terr = terrain.terrain_geotiff_elevation_apply(terr, self.osm.ddd_proj)
        terr = terr.material(ddd.mats.terrain)

        self.osm.ground_3d = terr

    def generate_areas_3d(self):
        logger.info("Generating 3D areas (%d)", len(self.osm.areas_2d.children))
        for area_2d in self.osm.areas_2d.children:
            try:
                if area_2d.extra.get('ddd:area:type', None) is None:
                    area_3d = self.generate_area_3d(area_2d)
                elif area_2d.extra['ddd:area:type'] == 'pitch':
                    area_3d = self.generate_area_3d_pitch(area_2d)
                else:
                    raise AssertionError("Area type undefined.")

                self.osm.areas_3d.children.append(area_3d)
            except ValueError as e:
                logger.warn("Could not generate area %s: %s", area_2d, e)
                raise
            except IndexError as e:
                logger.warn("Could not generate area %s: %s", area_2d, e)
                raise

    def generate_area_3d(self, area_2d):

        if area_2d.geom is not None:

            if area_2d.geom.type in ('GeometryCollection', 'MultiPolygon'):
                logger.debug("Generating area 3d as separate areas as it is a GeometryCollection: %s", area_2d)
                # FIXME: We might do this in extrude_step, like we do in triangulate and extrude, but difficult as it is in steps.
                # But also, we should have an individualize that work, correct iterators, and a generic cleanup/flatten method
                # to flatten areas, which might solve this.
                areas_3d = []
                for a in area_2d.individualize().children:
                    areas_3d.append(self.generate_area_3d(a))
                return ddd.group(areas_3d, empty=3)

            if area_2d.extra.get('_ddd:area', None) == 'park':

                area_3d = area_2d.extrude_step(area_2d.buffer(-1.0), 0.1, base=False)
                area_3d = area_3d.extrude_step(area_2d.buffer(-3.0), 0.1)

                #area_3d = ddd.group([area_2d.triangulate().translate([0, 0, 0.0]),
                #                     area_2d.buffer(-1.0).triangulate().translate([0, 0, 0.2]),
                #                     area_2d.buffer(-3.0).triangulate().translate([0, 0, 0.3])])

                area_3d = area_3d.translate([0, 0, 0])

            else:
                try:
                    height = area_2d.extra.get('ddd:height', 0.2)
                    if height:
                        area_3d = area_2d.extrude(-0.5 - height).translate([0, 0, height])
                    else:
                        area_3d = area_2d.triangulate()
                    area_3d = ddd.uv.map_cubic(area_3d)
                except DDDException as e:
                    logger.error("Could not generate area: %s (%s)", e, e.ddd_obj)
                    area_3d = DDDObject3()

        else:
            if len(area_2d.children) == 0:
                logger.warning("Null area geometry (children?): %s", area_2d)
            area_3d = DDDObject3()

        if area_3d.mesh:
            area_3d = terrain.terrain_geotiff_elevation_apply(area_3d, self.osm.ddd_proj)
            height = area_2d.extra.get('ddd:height', 0.2)

        area_3d.children = [self.generate_area_3d(c) for c in area_2d.children]

        return area_3d

    def generate_area_3d_pitch(self, area_2d):

        logger.info("Pitch: %s", area_2d)
        area_3d = self.generate_area_3d(area_2d)

        # TODO: pass size then adapt to position and orientation, easier to construct and reuse

        lines = sports.football_field_lines(area_2d)
        if lines:
            lines = terrain.terrain_geotiff_elevation_apply(lines, self.osm.ddd_proj).translate([0, 0, 0.15])
            height = area_2d.extra.get('ddd:height', 0.2)
            lines = lines.translate([0, 0, height])

            area_3d = ddd.group3([area_3d, lines])
        else:
            logger.debug("No pitch lines generated.")

        return area_3d

# ddd - D1D2D3
# Library for simple scene modelling.
# Jose Juan Montes 2020

import logging

from ddd.core.exception import DDDException
from ddd.ddd import DDDObject2, DDDObject3
from ddd.ddd import ddd
from ddd.geo import terrain
from ddd.pack.sketchy import plants, urban, sports
import traceback


# Get instance of logger for this module
logger = logging.getLogger(__name__)

class Areas3DOSMBuilder():

    max_trees = None

    def __init__(self, osmbuilder):

        self.osm = osmbuilder


    '''
    def generate_coastline_3d(self, area_crop):


        logger.info("Generating water and land areas according to coastline: %s", (area_crop.bounds))

        #self.water_3d = terrain.terrain_grid(self.area_crop.bounds, height=0.1, detail=200.0).translate([0, 0, 1]).material(mat_sea)

        water = ddd.rect(area_crop.bounds, name="Ground")
        coastlines = []
        coastlines_1d = []

        for way in self.osm.items_1d.children:
            if way.extra.get('osm:natural') == 'coastline':
                coastlines_1d.append(way)
                coastlines.append(way.buffer(0.01))
        #for way in self.osm.features.children:
        #    if way.properties.get('natural') == 'coastline':
        #        coastlines_1d.append(ddd.shape(way.geometry))
        #        coastlines.append(ddd.shape(way.geometry).buffer(0.1))

        logger.debug("Coastlines: %s", (coastlines_1d, ))
        if not coastlines:
            logger.info("No coastlines in the feature set.")
            return

        coastlines = ddd.group(coastlines)
        coastlines_1d = ddd.group(coastlines_1d)
        coastline_areas = water.subtract(coastlines)
        #coastline_areas.save("/tmp/test.svg")
        #coastline_areas.dump()

        # Generate coastline
        if coastlines_1d.children:
            coastlines_3d = coastlines_1d.intersection(water)
            coastlines_3d = coastlines_3d.individualize().extrude(10.0).translate([0, 0, -10.0])
            coastlines_3d = terrain.terrain_geotiff_elevation_apply(coastlines_3d, self.osm.ddd_proj)
            coastlines_3d = ddd.uv.map_cubic(coastlines_3d)
            coastlines_3d.name = 'Coastline: %s' % coastlines_3d.name
            self.osm.other_3d.append(coastlines_3d)


        areas = []
        areas_2d = []
        geoms = coastline_areas.geom.geoms if coastline_areas.geom.type == 'MultiPolygon' else [coastline_areas.geom]
        for water_area_geom in geoms:
            # Find closest point, closest segment, and angle to closest segment
            water_area_geom = ddd.shape(water_area_geom).clean(eps=0.01).geom

            if not water_area_geom.is_simple:
                logger.error("Invalid water area geometry (not simple): %s", water_area_geom)
                continue

            water_area_point = water_area_geom.representative_point()
            p, segment_idx, segment_coords_a, segment_coords_b, closest_obj, closest_d = coastlines_1d.closest_segment(ddd.shape(water_area_point))
            pol = LinearRing([segment_coords_a, segment_coords_b, water_area_point.coords[0]])

            if not pol.is_ccw:
                #area_3d = area_2d.extrude(-0.2)
                area_2d = ddd.shape(water_area_geom).buffer(0.10).clean(eps=0.01)
                area_2d.validate()
                area_2d = area_2d.material(ddd.mats.sea)

                area_3d = area_2d.triangulate().translate([0, 0, -0.5])
                area_3d.extra['ddd:collider'] = False
                area_3d.extra['ddd:shadows'] = False
                area_3d.extra['ddd:occluder'] = False
                areas_2d.append(area_2d)
                areas.append(area_3d)

        if areas:
            self.osm.water_3d = ddd.group(areas)
            self.osm.water_2d = ddd.group(areas_2d)
        else:
            logger.debug("No water areas from coastline generated.")
        pass
    '''

    '''
    def generate_ground_3d(self, area_crop):

        logger.info("Generating 3D terrain (bounds: %s)", area_crop.bounds)

        terr = self.osm.ground_2d

        # The buffer is fixing a core segment violation :/
        #terr.save("/tmp/test.svg")
        #terr.dump()
        #terr.show()
        #terr = ddd.group([DDDObject2(geom=s.buffer(0.5).buffer(-0.5)) for s in terr.geom.geoms if not s.is_empty])

        #terr.save("/tmp/test.svg")
        #terr = terr.triangulate()
        try:
            #terr = terr.individualize()
            #terr.validate()
            logger.warning("There's a buffer(0.000-0.001) operation which shouldn't be here: improve and use 'clean()'.")
            terr = terr.buffer(0.001)
            #terr = terr.buffer(0.0)
            #terr = terr.clean(eps=0.001)

            #terr = terr.extrude(0.3)
            terr = terr.triangulate()
        except ValueError as e:
            logger.error("Cannot generate terrain (FIXME): %s", e)
            raise DDDException("Coould not generate terrain: %s" % e, ddd_obj=terr)

        terr = terrain.terrain_geotiff_elevation_apply(terr, self.osm.ddd_proj)

        self.osm.ground_3d.append(terr)
    '''


    def generate_area_3d(self, area_2d):

        logger.debug("Generating area 3D for: %s", area_2d)

        if area_2d.get('ddd:area:type', None) == 'pitch':
            return self.generate_area_3d_pitch(area_2d)
        elif area_2d.get('ddd:area:type', None) == 'water':
            return self.generate_area_3d_water(area_2d)
        elif area_2d.get('ddd:area:type', None) == 'sea':
            return self.generate_area_3d_water(area_2d)
        elif area_2d.get('ddd:area:type', None) == 'underwater':
            return self.generate_area_3d_underwater(area_2d)
        elif area_2d.get('ddd:area:type', None) == 'railway':
            return self.osm.ways3.generate_way_3d_railway(area_2d)
        elif area_2d.get('ddd:area:type', None) == 'ignore':
            return None
        else:
            return self.generate_area_3d_gen(area_2d)

    def generate_area_3d_gen(self, area_2d):

        if area_2d.geom is not None and area_2d.geom.type != "LineString" and area_2d.geom.type:

            if area_2d.geom.type in ('GeometryCollection', 'MultiPolygon'):
                logger.debug("Generating area 3d as separate areas as it is a GeometryCollection: %s", area_2d)
                # FIXME: We might do this in extrude_step, like we do in triangulate and extrude, but difficult as it is in steps.
                # But also, we should have an individualize that work, correct iterators, and a generic cleanup/flatten method
                # to flatten areas, which might solve this.
                areas_3d = []
                for a in area_2d.individualize().clean_replace().children:
                    areas_3d.append(self.generate_area_3d(a))
                return ddd.group3(areas_3d, extra=area_2d.extra)

            if area_2d.extra.get('ddd:area:type', None) == 'raised':

                area_3d = area_2d.extrude_step(area_2d.buffer(-1.0), 0.1, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-3.0), 0.1, method=ddd.EXTRUSION_METHOD_SUBTRACT)

            elif area_2d.extra.get('ddd:area:type', None) == 'park':

                area_3d = area_2d.extrude_step(area_2d.buffer(-1.0), 0.1, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-3.0), 0.1, method=ddd.EXTRUSION_METHOD_SUBTRACT)

                # Grass
                # TODO: Add in a separate (optional) pass
                if False:
                    # For volumetric grass, as described by: https://www.bruteforce-games.com/post/grass-shader-devblog-04
                    grass_layers = []
                    colors = ['#000000', '#222222', '#444444', '#666666', '#888888', '#aaaaaa', '#cccccc', '#eeeeee']
                    for i in range(8):
                        grass_layer = area_3d.copy(name="Grass %d: %s" % (i, area_3d.name))
                        grass_layer = grass_layer.material(ddd.material(name="VolumetricGrass", color=colors[i], extra={'ddd:export-as-marker': True}))
                        #grass_layer.extra['ddd:vertex_colors'] =
                        grass_layer = grass_layer.translate([0, 0, 0.05 * i])
                        #grass_layer = terrain.terrain_geotiff_elevation_apply(grass_layer, self.osm.ddd_proj)
                        grass_layer.extra['ddd:shadows'] = False
                        grass_layer.extra['ddd:collider'] = False
                        grass_layer.extra['ddd:occluder'] = False
                        grass_layers.append(grass_layer)
                    #self.osm.other_3d.append(grass_layers)  #ddd.group3([area_3d, grass_layers])
                    area_3d.children.extend(grass_layers)


                #area_3d = ddd.group([area_2d.triangulate().translate([0, 0, 0.0]),
                #                     area_2d.buffer(-1.0).triangulate().translate([0, 0, 0.2]),
                #                     area_2d.buffer(-3.0).triangulate().translate([0, 0, 0.3])])

                #area_3d = area_3d.translate([0, 0, 0])

            elif area_2d.extra.get('ddd:area:type', None) == 'rocky':
                # Raise surface, then add random noise

                area_3d = area_2d.extrude_step(area_2d.buffer(-0.3), 0.3, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-1.5), 1.2, method=ddd.EXTRUSION_METHOD_SUBTRACT)

                # TODO:
                #last_cap_idx = result.extra.get('_extrusion_last_cap_idx', None)
                #if last_cap_idx is not None:
                #    faces = faces[:last_cap_idx]

                # Subdivide and apply noise / tag to avoid further subdivisions (check if other surfaces can be tagged too, eg, playgrounds, etc)

            elif area_2d.extra.get('ddd:area:type', None) == 'bunker':

                area_3d = area_2d.extrude_step(area_2d.buffer(-1.0), -0.4, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-3.0), -0.3, method=ddd.EXTRUSION_METHOD_SUBTRACT)

            elif area_2d.extra.get('ddd:area:type', None) == 'steps':
                # This is the steps area, not the stairs.
                area_3d = area_2d.extrude_step(area_2d, area_2d.extra['ddd:steps:height'], base=False)
                for stepidx in range(1, area_2d.extra['ddd:steps:count'] + 1):
                    area_3d = area_3d.extrude_step(area_2d.buffer(-area_2d.extra['ddd:steps:depth'] * stepidx), 0, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                    area_3d = area_3d.extrude_step(area_2d.buffer(-area_2d.extra['ddd:steps:depth'] * stepidx), area_2d.extra['ddd:steps:height'], method=ddd.EXTRUSION_METHOD_SUBTRACT)
                # TODO: Crop in 3D (or as a workaround fake it as centroid cropping)

            elif area_2d.extra.get('ddd:area:type', None) == 'sidewalk':

                area_3d = None

                try:
                    height = area_2d.extra.get('ddd:height', 0.2)
                    #area_3d = area_2d.extrude(-0.5 - height).translate([0, 0, height])
                    #area_3d = ddd.uv.map_cubic(area_3d)

                    add_kerb = True
                    if add_kerb:
                        try:
                            interior_original = area_2d.get('ddd:area:original').buffer(-0.3)
                            interior = area_2d.intersection(interior_original)
                            if not interior.is_empty():

                                kerb_3d = None
                                kerb_2d = area_2d.get('ddd:area:original').subtract(interior_original).intersection(area_2d).intersection(self.osm.area_crop2)
                                kerb_2d = kerb_2d.clean(eps=-0.01)
                                if not kerb_2d.is_empty():
                                    kerb_3d = kerb_2d.extrude(-0.5 - height).translate([0, 0, height]).material(ddd.mats.cement)
                                    kerb_3d = ddd.uv.map_cubic(kerb_3d)

                                area_2d_no_kerb = area_2d.subtract(kerb_2d).clean(eps=-0.01)
                                if not area_2d_no_kerb.is_empty():
                                    area_3d = area_2d_no_kerb.extrude(-0.5 - height).translate([0, 0, height])
                                    area_3d = ddd.uv.map_cubic(area_3d)
                                else:
                                    area_2d = area_2d.copy3()

                                if area_3d:

                                    area_3d.copy_from(area_2d)
                                    if area_3d.get('ddd:layer', '0') == '0': area_3d = ddd.meshops.remove_faces_pointing(area_3d, ddd.VECTOR_DOWN)  # TODO: Remove bases in generic way?

                                    if kerb_3d:
                                        area_3d.append(kerb_3d)
                                        #ddd.group2([area_2d.get('ddd:area:original'), area_2d.material(ddd.MAT_HIGHLIGHT), kerb_2d.material(ddd.mats.red)]).triangulate().show()

                            else:
                                logger.info("Cannot create kerb (empty interior) for area: %s", area_2d)
                                area_3d = None
                        except Exception as e:
                            logger.info("Error creating kerb for area %s: %s", area_2d, e)
                            print(traceback.format_exc())
                            #ddd.group2([area_2d.get('ddd:area:original'), area_2d.material(ddd.MAT_HIGHLIGHT)]).triangulate().show()
                            area_3d = None

                    # If no kerb or kerb could not be generated, just generate the area:
                    if area_3d is None:
                        logger.debug("No kerb generated, generating simple area: %s", area_2d)
                        area_3d = area_2d.extrude(-0.5 - height).translate([0, 0, height])
                        # Remove base
                        if area_3d.get('ddd:layer', '0') == '0':
                            area_3d = ddd.meshops.remove_faces_pointing(area_3d, ddd.VECTOR_DOWN)
                        area_3d = ddd.uv.map_cubic(area_3d)


                except Exception as e:
                    logger.error("Could not generate area: %s (%s)", e, area_2d)
                    area_3d = DDDObject3()

            elif area_2d.extra.get('ddd:area:type', None) == 'void':
                area_3d = area_2d.copy3("Void area: %s" % area_2d.name)

            else:
                logger.debug("Generating Area: %s" % area_2d)

                # Validate area (areas should be correct at this point, but this avoids core dumps in triangulate())
                try:
                    area_2d = area_2d.clean(eps=-0.01)  # 0.01 didn't work for fixing errors
                    area_2d.validate()
                except Exception as e:
                    logger.warn("Invalid area %s: %s", area_2d, e)
                    return None


                try:
                    height = area_2d.extra.get('ddd:area:height', area_2d.extra.get('ddd:height', 0.2))
                    if not height:
                        height = 0

                    # We extrude base_height to avoid sidewalks floating with no side triangles
                    base_height = area_2d.get('ddd:height:base', 0)
                    height = height + base_height

                    if height:
                        area_3d = area_2d.extrude(-0.5 - height).translate([0, 0, height])

                        # Remove base
                        if area_3d.get('ddd:layer', '0') == '0':
                            area_3d = ddd.meshops.remove_faces_pointing(area_3d, ddd.VECTOR_DOWN)

                    else:
                        area_3d = area_2d.triangulate()
                    area_3d = ddd.uv.map_cubic(area_3d)
                except Exception as e:
                    logger.error("Could not generate area: %s (%s)", e, area_2d)
                    area_3d = DDDObject3()

        else:
            if len(area_2d.children) == 0:
                logger.warning("Null area geometry (children?): %s", area_2d)
            area_3d = DDDObject3()

        # Subdivide
        if int(ddd.data.get('ddd:area:subdivide', 0)) > 0:
            #logger.debug("Subdividing: %s" % area_3d)
            #area_3d = area_3d.subdivide_to_size(float(ddd.data.get('ddd:area:subdivide')))
            area_3d = ddd.meshops.subdivide_to_grid(area_3d, float(ddd.data.get('ddd:area:subdivide')))
            area_3d.merge_vertices()  # Smoothes surface by unifying normals (modifies in place)

        area_3d = ddd.uv.map_cubic(area_3d)

        # Apply elevation
        area_3d = self.generate_area_3d_apply_elevation(area_2d, area_3d)

        #area_3d.extra = dict(area_2d.extra)
        area_3d.copy_from(area_2d)

        area_3d.children.extend( [self.generate_area_3d(c) for c in area_2d.children] )

        return area_3d

    def generate_area_3d_apply_elevation(self, area_2d, area_3d):

        apply_layer_height = True

        if area_3d.mesh or area_3d.children:
            #height = area_2d.extra.get('ddd:height', 0.2)
            area_elevation = area_2d.extra.get('ddd:area:elevation', 'geotiff')
            if area_elevation == 'geotiff':
                area_3d = terrain.terrain_geotiff_elevation_apply(area_3d, self.osm.ddd_proj)
            elif area_elevation == 'min':
                area_3d = terrain.terrain_geotiff_min_elevation_apply(area_3d, self.osm.ddd_proj)
            elif area_elevation == 'max':
                area_3d = terrain.terrain_geotiff_max_elevation_apply(area_3d, self.osm.ddd_proj)
            elif area_elevation == 'path':
                # logger.debug("3D layer transition: %s", way)
                # if way.extra['ddd:layer_transition']:
                if ('way_1d' in area_3d.extra):
                    path = area_3d.extra['way_1d']
                    vertex_func = self.osm.ways1.get_height_apply_func(path)
                    area_3d = area_3d.vertex_func(vertex_func)

                    apply_layer_height = False  # ddd:height:base is also not applied, as it is applied during area creation (extruded, to avoid

                area_3d = terrain.terrain_geotiff_elevation_apply(area_3d, self.osm.ddd_proj)

            elif area_elevation == 'water':
                apply_layer_height = False
                pass
            elif area_elevation == 'none':
                pass
            else:
                raise AssertionError()

        if apply_layer_height:
            layer = str(area_3d.extra.get('ddd:layer', area_3d.extra.get('osm:layer', 0)))
            # TODO: This ddd:base_height conflicts with ddd:height:base?
            base_height = float(area_3d.extra.get('ddd:base_height', self.osm.ways1.layer_height(layer)))
            area_3d = area_3d.translate([0, 0, base_height])

        # Commented as ways were using this but they are extruded to height
        #base_height = area_2d.get('ddd:height:base', None)
        #if base_height:
        #    area_3d = area_3d.translate([0, 0, base_height])

        return area_3d


    def generate_area_3d_pitch(self, area_2d):

        if area_2d.geom is None or area_2d.geom.is_empty:
            return None

        area_2d_orig = area_2d.extra.get('ddd:crop:original')  #, area_2d)

        #logger.debug("Pitch: %s", area_2d)
        area_3d = self.generate_area_3d_gen(area_2d)

        # TODO: pass size then adapt to position and orientation, easier to construct and reuse
        # TODO: get area uncropped (create a cropping utility that stores the original area)

        sport_full = area_2d.extra.get('ddd:sport', None)
        sport = sport_full.split(";")[0]  # Get first value if multivalued

        lines = None
        if sport == 'tennis':
            lines = sports.field_lines_area(area_2d_orig, sports.tennis_field_lines, padding=2.5)
        elif sport == 'basketball':
            lines = sports.field_lines_area(area_2d_orig, sports.basketball_field_lines, padding=1)
        elif sport == 'gymnastics':
            #lines = sports.field_lines_area(area_2d_orig, sports.basketball_field_lines, padding=2.0)
            lines = ddd.group3()
        elif sport in ('handball'):
            lines = sports.field_lines_area(area_2d_orig, sports.handball_field_lines, padding=1)
        elif sport in ('soccer', 'futsal'):
            lines = sports.field_lines_area(area_2d_orig, sports.football_field_lines, padding=1)
        else:
            # No sport assigned
            lines = ddd.group3()

        if lines:
            lines = terrain.terrain_geotiff_elevation_apply(lines, self.osm.ddd_proj)#.translate([0, 0, 0.01])
            height = area_2d.extra.get('ddd:height', 0.0)
            lines = lines.translate([0, 0, height])

            area_3d = ddd.group3([area_3d, lines])
        else:
            logger.debug("No pitch lines generated.")

        return area_3d

    def generate_area_3d_water(self, area_2d):
        area_3d = self.generate_area_3d_gen(area_2d)

        # Move water down, to account for waves
        area_3d = area_3d.translate([0, 0, -0.5])
        return area_3d

    def generate_area_3d_underwater(self, area_2d):
        logger.info ("Generating underwater for: %s", area_2d)
        #area_2d.dump()
        areas_2d = area_2d.individualize().flatten().clean()
        #area_2d.show()

        result = ddd.group3()
        for area_2d in areas_2d.children:

            area_2d = area_2d.clean()
            try:
                area_2d.validate()
            except DDDException as e:
                logger.error("Could not generate underwater area (invalid area %s): %s", area_2d, e)
                continue

            if area_2d.geom.type == "LineString":
                logger.error("Could not generate underwater area (area is line): %s", area_2d)
                continue

            try:
                area_3d = area_2d.extrude_step(area_2d.buffer(-1.0), -0.3, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-2.0), -0.5, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-4.0), -1.0, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-6.0), -0.5, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-9.0), -0.4, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-12.0), -0.3, method=ddd.EXTRUSION_METHOD_SUBTRACT)
            except Exception as e:
                logger.warn("Exception extruding underwater area (reduced LinearRings need caring): %s", e)
                print(area_2d.geom)
                print(area_2d.buffer(-1.0).geom)
                area_3d = None

            if area_3d is None or area_3d.extra['_extrusion_steps'] < 3:
                logger.debug("Could not extrude underwater area softly. Extruding abruptly.")
                area_3d = area_2d.extrude_step(area_2d.buffer(-0.05), -1.0, base=False, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-0.15), -0.5, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-0.3), -0.5, method=ddd.EXTRUSION_METHOD_SUBTRACT)
                area_3d = area_3d.extrude_step(area_2d.buffer(-1.0), -0.5, method=ddd.EXTRUSION_METHOD_SUBTRACT)
            if area_3d.extra['_extrusion_steps'] < 1:
                logger.warn("Could not extrude underwater area: %s", area_3d)
                area_3d = area_3d.translate([0, 0, -1.0])
            if area_3d: result.append(area_3d)

        result = terrain.terrain_geotiff_elevation_apply(result, self.osm.ddd_proj)
        #result.show()

        return result

# ddd - D1D2D3
# Library for simple scene modelling.
# Jose Juan Montes 2020

import argparse
from functools import partial
import logging
import os
import subprocess

from PyTexturePacker import Packer
import geojson
import pyproj
from shapely import ops

from ddd.core.cli import D1D2D3Bootstrap
from ddd.core.command import DDDCommand
from ddd.ddd import ddd
from ddd.geo import terrain
from ddd.osm import osm


#from osm import OSMDDDBootstrap
# Get instance of logger for this module
logger = logging.getLogger(__name__)


class TexturePackCommand(DDDCommand):

    def parse_args(self, args):

        #program_name = os.path.basename(sys.argv[0])
        parser = argparse.ArgumentParser()  # description='', usage = ''

        #parser.add_argument("-w", "--worker", default=None, help="worker (i/n)")
        parser.add_argument("-l", "--limit", type=int, default=None, help="tasks limit")
        parser.add_argument("--name", type=str, default=None, help="base name for output")
        parser.add_argument("--center", type=str, default=None, help="center of target area")
        parser.add_argument("--radius", type=float, default=None, help="radius of target area")
        #parser.add_argument("--area", type=str, help="GeoJSON polygon of target area")
        #parser.add_argument("--tile", type=float, help="tile size in meters (0 for entire area)")

        args = parser.parse_args(args)
        self.limit = args.limit

        center = args.center.split(",")
        self.center = (float(center[0]), float(center[1]))

        self.name = args.name

        self.radius = args.radius

    def pack_test():
        # create a MaxRectsBinPacker
        packer = Packer.create(max_width=2048, max_height=2048, bg_color=0xffffff00)
        # pack texture images under directory "test_case/" and name the output images as "test_case".
        # "%d" in output file name "test_case%d" is a placeholder, which is a multipack index, starting with 0.
        packer.pack("es/", "traffic_signs_es_%d")

    pack_test()

    def run(self):

        # TODO: Move to pipelined builder
        logger.warn("Move to builder")

        logger.info("Running DDD123 OSM build command.")

        D1D2D3Bootstrap._instance._unparsed_args = None

        tasks_count = 0

        # TODO: allow alias in ~/.ddd.conf
        vigo_wgs84 = [-8.723, 42.238]
        cuvi_wgs84 = [-8.683, 42.168]
        area_vigo = { "type": "Polygon", "coordinates": [ [ [ -8.738025517345417, 42.223436382101397 ], [ -8.740762525671032, 42.229564900743533 ], [ -8.73778751662145, 42.23289691087907 ], [ -8.738620519155333, 42.235871919928648 ], [ -8.733920004856994, 42.241702937665828 ], [ -8.729516991463614, 42.242773940923676 ], [ -8.724102474993376, 42.244975447620369 ], [ -8.712142938614059, 42.246254701511681 ], [ -8.711190935718193, 42.245748949973255 ], [ -8.703842663365727, 42.244112694995998 ], [ -8.700570153411187, 42.241197186127408 ], [ -8.702057657935978, 42.238995679430715 ], [ -8.70289066046986, 42.235485168752206 ], [ -8.705865669519442, 42.231736657349735 ], [ -8.70907867929299, 42.23036815318693 ], [ -8.716278201192978, 42.229059149205113 ], [ -8.719610211328508, 42.225370137983631 ], [ -8.726750233047504, 42.219539120246452 ], [ -8.730379744087994, 42.217516114092739 ], [ -8.736210761825173, 42.2191821191605 ], [ -8.736210761825173, 42.2191821191605 ], [ -8.738174267797897, 42.221562126400165 ], [ -8.738174267797897, 42.221562126400165 ], [ -8.738025517345417, 42.223436382101397 ] ] ] }
        area_vigo_huge_rande = { "type": "MultiPolygon", "coordinates": [ [ [ [ -8.678739229779634, 42.285406246127017 ], [ -8.679768244461799, 42.286124008658462 ], [ -8.679944646978743, 42.287581258944734 ], [ -8.679709443622819, 42.290212924049762 ], [ -8.680473854529568, 42.292192037766931 ], [ -8.68123826543632, 42.293540409297322 ], [ -8.680326852432117, 42.296345799483696 ], [ -8.67829822348728, 42.296019597743189 ], [ -8.676534198317855, 42.296367546206326 ], [ -8.673329552593403, 42.296258812518111 ], [ -8.67153612700449, 42.297955036674374 ], [ -8.668243280021565, 42.299129318941247 ], [ -8.665009233877623, 42.299738197421469 ], [ -8.661275380602341, 42.30252156692557 ], [ -8.652602256852674, 42.303152156982897 ], [ -8.648603799801982, 42.298759639848647 ], [ -8.641165493670913, 42.289147221675357 ], [ -8.65072063000529, 42.282382853576621 ], [ -8.65730632397114, 42.275465481810826 ], [ -8.65965835753037, 42.268242761434706 ], [ -8.661657586055718, 42.260758105800491 ], [ -8.664597628004756, 42.257189526957589 ], [ -8.676240194122952, 42.251009315195994 ], [ -8.676475397478876, 42.245350843851035 ], [ -8.651308638395097, 42.239953059756857 ], [ -8.63943086892098, 42.244741439740103 ], [ -8.620496998769166, 42.249181249186741 ], [ -8.612147279633895, 42.243870852227474 ], [ -8.618144965209934, 42.226543662551634 ], [ -8.628493912870553, 42.213566923726354 ], [ -8.647192579666443, 42.210082781391023 ], [ -8.654366282022099, 42.200674637101095 ], [ -8.654601485378024, 42.190132366865519 ], [ -8.663421611225139, 42.175492249420188 ], [ -8.672476940428181, 42.164509936746896 ], [ -8.666949661563988, 42.158059118335679 ], [ -8.666949661563988, 42.154048818664116 ], [ -8.682355481376954, 42.151782015135495 ], [ -8.698584512935652, 42.151956387519974 ], [ -8.707522240460731, 42.154397550462775 ], [ -8.715166349528236, 42.158756535815868 ], [ -8.726103305578659, 42.167473605784153 ], [ -8.732806601222471, 42.173139057222009 ], [ -8.735041033103739, 42.180982690717805 ], [ -8.742685142171242, 42.189173891460896 ], [ -8.762559825746747, 42.185688403840906 ], [ -8.7798472724071, 42.182987018755384 ], [ -8.786903373084794, 42.188041129063663 ], [ -8.795605897253949, 42.187256897051611 ], [ -8.80536683652476, 42.191744315452596 ], [ -8.808248077634818, 42.2020249661402 ], [ -8.796664312355604, 42.206990444093883 ], [ -8.792077846915102, 42.202939688770883 ], [ -8.780905687508753, 42.212608803743251 ], [ -8.782493310161234, 42.223582762359229 ], [ -8.764500253433113, 42.235425529931319 ], [ -8.743625955594931, 42.241781393183061 ], [ -8.719870416646694, 42.248049562726422 ], [ -8.709756672341998, 42.260366442379272 ], [ -8.691763615613878, 42.264500544688026 ], [ -8.688235565275031, 42.262498802682778 ], [ -8.678357024326258, 42.271506141210914 ], [ -8.66950749805965, 42.283774937233652 ], [ -8.669514848164527, 42.286255869446485 ], [ -8.669597536844341, 42.286667762707708 ], [ -8.669812527411864, 42.286814575496322 ], [ -8.670181870181713, 42.28682680987994 ], [ -8.678739229779634, 42.285406246127017 ] ] ] ] }
        #name = "vilanovailagertru"


        #name = "vigo"
        #center_wgs84 = vigo_wgs84
        #area = area_vigo_huge_rande
        center_wgs84 = self.center
        area = None

        # Name
        if self.name is None:
            self.name = "ddd-osm-%.3f,%.3f" % center_wgs84
        name = self.name

        path = "data/osm/"

        # Prepare data
        # Check if geojson file is available
        if not os.path.isfile(os.path.join(path, "%s.osm.geojson" % name)):
            logger.info("Data path file %s not found. Trying to produce data.")
            self.get_data(path, name, center_wgs84, area)

        osm_proj = pyproj.Proj(init='epsg:4326')  # FIXME: API reocmends using only 'epsg:4326' but seems to give weird coordinates?
        ddd_proj = pyproj.Proj(proj="tmerc",
                               lon_0=center_wgs84[0], lat_0=center_wgs84[1],
                               k=1,
                               x_0=0., y_0=0.,
                               units="m", datum="WGS84", ellps="WGS84",
                               towgs84="0,0,0,0,0,0,0",
                               no_defs=True)

        files = [os.path.join(path, f) for f in [name + '.osm.geojson'] if os.path.isfile(os.path.join(path, f)) and f.endswith(".geojson")]
        logger.info("Reading %d files from %s" % (len(files), path))

        # Polygon area
        area_ddd = None
        if area:
            area = ddd.geometry(area).geom
            trans_func = partial(pyproj.transform, osm_proj, ddd_proj)
            area_ddd = ops.transform(trans_func, area)
            logger.info("Polygon area: %.1f km2 (%d at 500, %d at 250, %d at 200)", (area_ddd.area / (1000 * 1000)), (area_ddd.area / (500 * 500)), (area_ddd.area / (250 * 250)), (area_ddd.area / (200 * 200)))

        # TODO: organise tasks and locks in pipeline, not here
        for (idx, (x, y)) in enumerate(range_around([-64, -64, 64, 64])):
        #for x, y in range_around([-8, -8, 8, 8]):  # -8, 3

            if self.limit and tasks_count >= self.limit:
                logger.info("Limit of %d tasks hit.", self.limit)
                break

            bbox_crop = [x * self.chunk_size, y * self.chunk_size, (x + 1) * self.chunk_size, (y + 1) * self.chunk_size]
            bbox_filter = [bbox_crop[0] - self.chunk_size_extra_filter, bbox_crop[1] - self.chunk_size_extra_filter,
                           bbox_crop[2] + self.chunk_size_extra_filter, bbox_crop[3] + self.chunk_size_extra_filter]
            shortname = '%s_%d_%d,%d' % (name, abs(x) + abs(y), bbox_crop[0], bbox_crop[1])
            filenamebase = 'output/%s/%s' % (name, shortname)
            filename = filenamebase + ".glb"

            area_crop = ddd.rect(bbox_crop).geom
            area_filter = ddd.rect(bbox_filter).geom

            if area_ddd and not area_ddd.intersects(area_crop):
                logger.debug("Skipping: %s (cropped area not contained in greater filtering area)", filename)
                #if os.path.exists(filename):
                #    logger.info("Deleting: %s", filename)
                #    os.unlink(filename)
                continue

            if not D1D2D3Bootstrap._instance.overwrite and os.path.exists(filename):
                logger.debug("Skipping: %s (already exists)", filename)
                continue

            # Try to lock
            lockfilename = filename + ".lock"
            try:
                with open(lockfilename, "x") as _:

                    old_formatters = {hdlr: hdlr.formatter for hdlr in logging.getLogger().handlers}
                    if D1D2D3Bootstrap._instance.debug:
                        new_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s [' + shortname + '] %(message)s')
                    else:
                        new_formatter = logging.Formatter('%(asctime)s [' + shortname + '] %(message)s')

                    for hdlr in logging.getLogger().handlers:
                        hdlr.setFormatter(new_formatter)

                    logger.info("Generating: %s", filename)

                    try:

                        osmbuilder = osm.OSMBuilder(area_crop=area_crop, area_filter=area_filter, osm_proj=osm_proj, ddd_proj=ddd_proj)
                        osmbuilder.load_geojson(files)
                        scene = osmbuilder.generate()
                        #scene.dump()
                        scene.save(filename)
                        scene.save("/tmp/dddosm.json")

                        osmbuilder.save_tile_2d(filenamebase + ".png")

                        #sys.exit(0)

                        tasks_count += 1

                    finally:

                        # Ensure lock file is removed
                        try:
                            os.unlink(lockfilename)
                        except Exception as e:
                            pass

                    for hdlr in logging.getLogger().handlers:
                        hdlr.setFormatter(old_formatters[hdlr])

            except FileExistsError as e:
                logger.info("Skipping: %s (lock file exists)", filename)



#self = OSMDDDBootstrap()
#self.parse_args(D1D2D3Bootstrap._instance._unparsed_args)
#D1D2D3Bootstrap._instance._unparsed_args = None

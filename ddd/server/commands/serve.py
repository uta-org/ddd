# ddd - D1D2D3
# Library for simple scene modelling.
# Jose Juan Montes 2020-2021

import argparse
import asyncio
from concurrent import futures
import concurrent
import logging
import sys

from aiohttp import web
import socketio
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from ddd.core import settings
from ddd.core.cli import D1D2D3Bootstrap
from ddd.core.command import DDDCommand
from ddd.ddd import DDDObject2, DDDObject3
from ddd.osm import osm
from ddd.pipeline.pipeline import DDDPipeline
import json
import os
import traceback


# Get instance of logger for this module
logger = logging.getLogger(__name__)


class RollbackImporter:
    """
    Monkey patches "import" to keep track of imported modules, in order to
    later remove and reload them if needed.
    """

    def __init__(self):
        "Creates an instance and installs as the global importer"
        self.previousModules = sys.modules.copy()
        self.realImport = __builtins__['__import__']
        __builtins__['__import__'] = self._import
        self.newModules = {}

    def _import(self, name, globals=None, locals=None, fromlist=[], *args):
        #print(fromlist)
        #print(args)
        #print(kwargs)
        #raise()
        result = self.realImport(*(name, globals, locals, fromlist, *args))
        self.newModules[name] = 1
        return result

    def uninstall(self):
        for modname in self.newModules.keys():
            if not modname in self.previousModules:
                # Force reload when modname next imported
                try:
                    del(sys.modules[modname])
                    logger.info("Uninstalled module from sys.modules for reload: %s", modname)
                except Exception as e:
                    logger.warn("Could not uninstall module from sys.modules for reload: %s", modname)
        __builtins__['__import__'] = self.realImport


class FileChangedEventHandler(FileSystemEventHandler):

    def __init__(self, dddserver):
        super().__init__()
        self.dddserver = dddserver

    def on_any_event(self, ev):

        logger.info("File monitoring event: %s", ev)

        if not isinstance(ev, FileModifiedEvent):
            return
        if not ev.src_path.endswith(".py"):
            return

        logger.info("Reloading pipeline.")
        try:
            self.dddserver.pipeline_reload()
        except Exception as e:
            logger.warn("Could not reload pipeline: %s", e)
            print(traceback.format_exc())
            return

        # TODO: Move this interface to ServerServeCommand
        asyncio.run_coroutine_threadsafe(self.dddserver.pipeline_run(), self.dddserver.loop)


class ServerServeCommand(DDDCommand):

    def parse_args(self, args):

        #program_name = os.path.basename(sys.argv[0])
        parser = argparse.ArgumentParser()  # description='', usage = ''

        #parser.add_argument("-w", "--worker", default=None, help="worker (i/n)")
        parser.add_argument("script", help="script or pipeline entry point")

        args = parser.parse_args(args)

        self.script = args.script

        self.files_changed = False
        self.rollbackImporter = None

    def run(self):

        logger.info("Starting DDD server tool API (ws://).")

        D1D2D3Bootstrap._instance._unparsed_args = None

        # Disable builtin rendering
        logger.info("Disabling builtin rendering.")
        D1D2D3Bootstrap.renderer = "none"

        self.loop = asyncio.get_event_loop()

        # Create pipeline
        self.pipeline = None
        self.running = False

        # Start python-socketio
        self.sio = socketio.AsyncServer(cors_allowed_origins='*')
        app = web.Application()
        self.sio.attach(app)

        async def index(request):
            """
            """
            #with open('index.html') as f:
            #    return web.Response(text=f.read(), content_type='text/html')
            return web.Response(text="DDD SocketIO API Server", content_type='text/html')

        @self.sio.event
        def connect(sid, environ):
            logger.info("Websocket connect: %s %s", sid, environ)

        @self.sio.event
        async def chat_message(sid, data):
            logger.info("Websocket chat_message: %s %s", sid, data)

        @self.sio.event
        async def status_get(sid, data):
            logger.info("Websocket status_get: %s %s", sid, data)
            status = self.status_get()
            #logger.debug("Sending status: %s", status)
            await self.sio.emit('status', status, room=sid)

        @self.sio.event
        async def result_get(sid, data):
            logger.info("Websocket result_get: %s %s", sid, data)
            await self.result_send(sid)

        @self.sio.event
        def disconnect(sid):
            logger.info('Websocket disconnect: %s', sid)

        #app.router.add_static('/static', 'static')
        app.router.add_get('/', index)

        # Run pipeline initially
        asyncio.ensure_future(self.pipeline_init())

        try:
            web.run_app(app, host="localhost", port=8085)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")


    def status2_get(self):
        status = {
            'script': self.script,
            'status': {
                'running': self.running,
            }
        }

    def status_get(self):

        tasks_sorted = self.pipeline.tasks_sorted()

        tasks = [{
            'name': t.name,
            'order': t.order,
            'order_num': t._order_num,

            'path': t.path,
            'condition': t.condition != None,
            'selector': t.selector.selector if t.selector else None,
            'filter': t.filter != None,
            'recurse': t.recurse,
            'replace': t.replace,

            'cache': t.cache,
            'cache_override': t.cache_override,

            #'funcargs': t._funcargs,
            'description': t._funcargs[0].__doc__,

            'params': t.params,

            'run_seconds': t._run_seconds,
            'run_selected': t._run_selected,
        } for t in tasks_sorted]

        # Serialize and deserialize to ensure data is JSON serializable (converts objects to strings)
        data = json.loads(json.dumps(self.pipeline.data, default=str))

        status = {
            'script': self.script,
            'data': data,
            'tasks': tasks
        }

        return status

    def format_node(self, node):
        """
        Formats nodes for dddserver representation.

        This includes transforming 2D to 3D nodes as needed.
        """
        if isinstance(node, DDDObject2):
            result = node.copy3()
            if node.geom:
                try:
                    triangulated = node.triangulate(ignore_children=True)
                    result.mesh = triangulated.mesh
                except Exception as e:
                    logger.warn("Could not triangulate 2D object for 3D representation export (%s): %s", node, e)
        else:
            result = node.copy()

        # Temporary hack to separate flat elements
        increment = 0.025
        accum = 0.0
        newchildren = []
        for c in node.children:
            nc = self.format_node(c)
            if isinstance(c, DDDObject2):
                accum += increment
                nc = nc.translate([0, 0, accum])
            newchildren.append(nc)

        result.children = newchildren

        return result

    def result_get(self):
        root = self.pipeline.root

        # Process result
        #if isinstance(root, DDDObject2):
        #    root = root.copy3(copy_children=True)
        #root = root.find("/Elements3")
        root = self.format_node(root)

        # Export
        try:
            result_data = root.save(".glb")
        except Exception as e:
            logger.error("Could not produce result model (.glb): %s", e)
            result_data = None

        return result_data

    async def result_send(self, sid=None):

        result = self.result_get()
        #return status
        if result:
            logger.info("Sending result: %s bytes", len(result))
            await self.sio.emit('result', {'data': result}, room=sid)
        else:
            logger.info("No result to send.")

    async def pipeline_init(self):
        #self.pipeline = DDDPipeline([self.script], name="DDD Server Build Pipeline")
        self.pipeline_reload()

        # Start file monitoring
        self.start_file_monitoring()

        # Run pipeline initially
        await self.pipeline_run()

    def pipeline_reload(self):
        #self.pipeline = None
        if self.rollbackImporter:
            self.rollbackImporter.uninstall()
        else:
            self.rollbackImporter = RollbackImporter()

        try:
            del(sys.modules[self.script.replace(".py", "")])
        except Exception as e:
            pass

        self.pipeline = DDDPipeline(self.script, name="DDD Server Build Pipeline")

    async def pipeline_run(self):

        if self.running:
            logger.warn("Pipeline already running.")
            return

        self.running = True

        with futures.ThreadPoolExecutor() as pool:
            logger.info("Running in thread pool.")

            run_result = await self.loop.run_in_executor(pool, self.pipeline_run_blocking)
            logger.info("Thread pool result: %s", run_result)

        self.running = False

        asyncio.ensure_future(self.result_send())

    def pipeline_run_blocking(self):
        try:
            self.pipeline.run()
        except Exception as e:
            logger.warn("Error running pipeline: %s", e)
            print(traceback.format_exc())
            return False

        return True

    def start_file_monitoring(self):

        event_handler = FileChangedEventHandler(self)

        path = self.script

        logger.info("Starting file monitoring.")
        observer = Observer()

        # Main file
        #observer.schedule(event_handler, path, recursive=False)

        # Main file dir recursively
        observer.schedule(event_handler, os.path.dirname(os.path.abspath(path)), recursive=True)

        # Imported files
        '''
        for modname in self.rollbackImporter.newModules.keys():
            logger.info("Monitoring: %s", modname)
            try:
                observer.schedule(event_handler, sys.modules[modname].__file__, recursive=False)
            except Exception as e:
                logger.info(e)
        '''

        observer.start()

        #try:
        #    while True:
        #        time.sleep(1)
        #except KeyboardInterrupt:

        # Stop file monitoring
        #observer.stop()
        #observer.join()

from flask import Flask
import threading
import psutil
import asyncio
from quart import Quart, request, make_response, jsonify
from ModbusClients import ModbusClients
import atexit
from setup_logging import setup_logging
from launch_params import handle_launch_params
from module_manager import ModuleManager

def cleanup(app):
    app.logger.info("cleanup function executed!")
    app.module_manager.cleanup_all()
    if app.clients is not None:
        app.clients.cleanup()

async def monitor_fault_poller(app):
    """
    Heathbeat monitor that makes sure fault poller
    stays alive and if it dies it restarts it
    """
    while True:
        if hasattr(app, 'fault_poller_pid'):
            pid = app.fault_poller_pid
            if pid and not psutil.pid_exists(pid):
                app.logger.warning(f"fault_poller (PID: {pid}) is not running, restarting...")
                new_pid = app.module_manager.launch_module("fault_poller")
                app.fault_poller_pid = new_pid
                app.logger.info(f"Restarted fault_poller with PID: {new_pid}")
                del app.module_manager.processes[pid]
        await asyncio.sleep(10)  # Check every 10 seconds

async def init(app):
    try:
        logger = setup_logging("server", "server.log")
        module_manager = ModuleManager(logger)
        config = handle_launch_params()
        clients = ModbusClients(config=config, logger=logger)

        fault_poller_pid = module_manager.launch_module("fault_poller")
        app.monitor_task = asyncio.create_task(monitor_fault_poller(app))

        # Connect to both drivers
        # await clients.connect()   

        app.app_config = config
        app.logger = logger
        app.module_manager = module_manager
        app.is_process_done = True
        app.fault_poller_pid = fault_poller_pid
        app.clients = clients

        atexit.register(lambda: cleanup(app))
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")

async def create_app():
    app = Quart(__name__)
    await init(app)

    @app.route("/write", methods=['post'])
    async def write():
        pass

    @app.route('/stop', methods=['GET'])
    async def stop_motors():
        try:
            success = await app.clients.stop()
            if not success:
                pass # do something crazy :O
        except Exception as e:
            app.logger.error("Failed to stop motors?") # Mitäs sitten :D

    return app

if __name__ == '__main__':
    async def run_app():
        app = await create_app()
        await app.run_task(port=app.app_config.WEB_SERVER_PORT)

    asyncio.run(run_app())
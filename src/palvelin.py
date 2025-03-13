from flask import Flask
import threading
import psutil
import asyncio
from quart import Quart
from ModbusClients import ModbusClients
state_lock = threading.Lock()
import atexit
from setup_logging import setup_logging
from launch_params import handle_launch_params
from module_manager import ModuleManager
import subprocess
from time import sleep

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
        with state_lock:
            if hasattr(app, 'fault_poller_pid'):
                pid = app.fault_poller_pid
                if pid and not psutil.pid_exists(pid):
                    app.logger.warning(f"fault_poller (PID: {pid}) is not running, restarting...")
                    new_pid = app.module_manager.launch_module("fault_poller")
                    app.fault_poller_pid = new_pid
                    app.logger.info(f"Restarted fault_poller with PID: {new_pid}")
                    del app.module_manager.processes[pid]
        asyncio.sleep(10)  # Check every 10 seconds

async def init(app):
    try:
        logger = setup_logging("server", "server.log")
        module_manager = ModuleManager(logger)
        config = handle_launch_params()
        clients = ModbusClients(config=config, logger=logger)

        # Connect to both drivers
        # await clients.connect()   

        # asyncio.create_task(monitor_fault_poller(app))

        app.app_config = config
        app.logger = logger
        app.module_manager = module_manager
        app.is_process_done = True
        # app.fault_poller_pid = fault_poller_pid
        app.clients = clients
        app.test = 1

        atexit.register(lambda: cleanup(app))
        # TODO - homee moottorit ja tarkista että se on homattu ja enabloi alternative operation mode
        # kun laittaa position osottamaan siihen missä se on paikallaan,
        # eli kato missä mottori on nyt ja laita analog 
        #modbus cntrl arvo osottamaan siihen kohtaan
        # yhistä moottoreihin ja returnaa moottoreiden connection
        # instancet apille joka asettaa ne global variableihin
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")

def create_app():
    app = Quart(__name__)
    init(app)

    # monitor_thread = threading.Thread(target=monitor_fault_poller, args=(app, ), daemon=True)
    # monitor_thread.start()

    # This setup happens only once when the app is created
    # Luodaan tässä houmaus ja global variablejen luonti
    
    # launch optionit
    
    @app.route('/update_var1', methods=['GET'])
    async def update_var1():
        with state_lock: # Varmistaa että tätä state ei muokata eri paikoista samaan aikaan (multi thread safe) s
            # Access and modify shared state
            app.is_process_done = False
            app.test = 3
        return f"Updated var1 to {app.is_process_done}"
    
    @app.route("/test", methods=['GET'])
    async def testing():
        while True:
            if app.test == 10:
                print("yee")
                break
            else:
                await asyncio.sleep(app.app_config.POS_UPDATE_HZ*0.1)
        return f"Moi", 200

    @app.route("/test2", methods=['GET'])
    async def testing2():
        app.test = 10 # hehe
        return f"Moi 2", 200

    @app.route("/write", methods=['post'])
    async def resolve_comms_fault():
        # check if acceleration curve is ready, if not wait with asyncio
        # stop motors
        #
        pass

    @app.route("/fault-reset", methods=['GET'])
    async def resolve_fault():
        pass

    @app.route('/read_var1', methods=['GET'])
    async def read_var1():
        with state_lock:
            # Access shared state for reading
            value = app.is_process_done
        return f"Current value of var1 is {value}"
    
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
    app = create_app()
    app.run(port=app.app_config.WEB_SERVER_PORT)
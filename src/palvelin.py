from flask import Flask
import threading
import psutil
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
    app.clients.cleanup()

def monitor_fault_poller(app):
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
        sleep(10)  # Check every 10 seconds

def init(app):
    try:
        logger = setup_logging("server", "server.log")
        module_manager = ModuleManager(logger)
        config = handle_launch_params()
        fault_poller_pid = module_manager.launch_module("fault_poller")
        clients = ModbusClients(config=config, logger=logger)

        app.app_config = config
        app.logger = logger
        app.module_manager = module_manager
        app.is_process_done = True
        app.fault_poller_pid = fault_poller_pid
        app.clients = clients

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
    app = Flask(__name__)
    init(app)

    monitor_thread = threading.Thread(target=monitor_fault_poller, args=(app, ), daemon=True)
    monitor_thread.start()
    
    # This setup happens only once when the app is created
    # Luodaan tässä houmaus ja global variablejen luonti
    
    # launch optionit
    
    @app.route('/update_var1', methods=['GET'])
    def update_var1():
        with state_lock: # Varmistaa että tätä state ei muokata eri paikoista samaan aikaan (multi thread safe) s
            # Access and modify shared state
            app.is_process_done = False
            app.test = 3
        return f"Updated var1 to {app.is_process_done}"

    @app.route('/read_var1', methods=['GET'])
    def read_var1():
        with state_lock:
            # Access shared state for reading
            value = app.is_process_done
        return f"Current value of var1 is {value}"
    
    @app.route('/stop', methods=['GET'])
    def stop_motors():

        pass # sammuta moottorit -> päivitä global var?

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(port=app.app_config.WEB_SERVER_PORT) ## TODO - tää varmaa tulee launch optioneist???
from flask import Flask
import psutil
import asyncio
from quart import Quart, request, make_response, jsonify
from ModbusClients import ModbusClients
import atexit
from setup_logging import setup_logging
from launch_params import handle_launch_params
from module_manager import ModuleManager
import subprocess
from time import sleep
from utils import is_nth_bit_on
import math

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

def convert_to_revs(pfeedback):
    decimal = pfeedback[0] / 65535
    num = pfeedback[1]
    return num + decimal

async def init(app):
    try:
        logger = setup_logging("server", "server.log")
        module_manager = ModuleManager(logger)
        config = handle_launch_params()
        clients = ModbusClients(config=config, logger=logger)

        fault_poller_pid = module_manager.launch_module("fault_poller")
        app.monitor_task = asyncio.create_task(monitor_fault_poller(app))

        # Connect to both drivers
        await clients.connect()   

        app.app_config = config
        app.logger = logger
        
        app.module_manager = module_manager
        app.is_process_done = True
        app.fault_poller_pid = fault_poller_pid
        app.clients = clients

        atexit.register(lambda: cleanup(app))
        
        homed = await clients.home()
        if homed:
            #MAX POSITION LIMITS FOR BOTH MOTORS | 147 mm
            await clients.client_right.write_registers(address=config.ANALOG_POSITION_MAXIMUM, values=[61406, 28], slave=config.SLAVE_ID)
            await clients.client_left.write_registers(address=config.ANALOG_POSITION_MAXIMUM, values=[61406, 28], slave=config.SLAVE_ID)

            #MIN POSITION LIMITS FOR BOTH MOTORS || 2 mm
            await clients.client_right.write_registers(address=config.ANALOG_POSITION_MINIMUM, values=[25801, 0], slave=config.SLAVE_ID)
            await clients.client_left.write_registers(address=config.ANALOG_POSITION_MINIMUM, values=[25801, 0], slave=config.SLAVE_ID)

            #Analog max velocity. Max speed for actuator is set to 338mm/sec, for testing we'll set it to 50mm/sec.
            #REVS = speed/lead. REVS = 50mm/s / 5.08mm/rev = 9,842519685039370078740157480315 REVS 
            await clients.client_right.write_registers(address=config.ANALOG_VEL_MAXIMUM, values=[55214, 9], slave=config.SLAVE_ID)
            await clients.client_left.write_registers(address=config.ANALOG_VEL_MAXIMUM, values=[55214, 9], slave=config.SLAVE_ID)

            #Analog max acceleration. This is set to 50 REVS/S/S for testing. | 254 mm/s/s
            await clients.client_right.write_registers(address=config.ANALOG_ACCELERATION_MAXIMUM, values=[0, 50], slave=config.SLAVE_ID)
            await clients.client_left.write_registers(address=config.ANALOG_ACCELERATION_MAXIMUM, values=[0, 50], slave=config.SLAVE_ID)

            #Analog input channel set to modbus ctrl
            await clients.client_right.write_register(address=config.ANALOG_INPUT_CHANNEL,value=2,slave=config.SLAVE_ID)
            await clients.client_left.write_register(address=config.ANALOG_INPUT_CHANNEL,value=2,slave=config.SLAVE_ID)

            #Read position feedback registers. 
            pfeedback_client_left = await clients.client_left.read_holding_registers(address=config.PFEEDBACK_POSITION, count=2, slave=config.SLAVE_ID)
            
            UPOS16_MAX = 65535
            revs_left = convert_to_revs(pfeedback_client_left)

            #Homed position for both actuators
            ## Percentile = x - pos_min / (pos_max - pos_min)
            ## Assuming that home is the same for both motors ( SHOULD BE !)
            POS_MIN_REVS = 0.393698024
            POS_MAX_REVS = 28.937007874015748031496062992126
            modbus_percentile = (revs_left - POS_MIN_REVS) / (POS_MAX_REVS - POS_MIN_REVS)
            max(0, min(modbus_percentile, 1))

            position_client_right = math.floor(modbus_percentile * UPOS16_MAX)
            position_client_left = math.floor(modbus_percentile * UPOS16_MAX)

            await clients.client_right.write_register(address=config.MODBUS_ANALOG_POSITION, value=position_client_right, slave=config.SLAVE_ID)
            await clients.client_left.write_register(address=config.MODBUS_ANALOG_POSITION, value=position_client_left, slave=config.SLAVE_ID)

            # TODO Ipeak pitää varmistaa vielä onhan 128 arvo = 1 Ampeeri 
            await clients.client_right.write_register(address=config.IPEAK,value=128,slave=config.SLAVE_ID)
            await clients.client_left.write_register(address=config.IPEAK,value=128,slave=config.SLAVE_ID)

            # Finally - Ready for operation
            await clients.client_right.write_register(address=config.COMMAND_MODE, value=2, slave=config.SLAVE_ID)
            await clients.client_left.write_register(address=config.COMMAND_MODE, value=2, slave=config.SLAVE_ID)
        
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
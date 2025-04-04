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
from utils import is_nth_bit_on, IEG_MODE_bitmask_enable, convert_acc_rpm_revs, convert_vel_rpm_revs
import math
import sys
import os
import time

async def shutdown_test(app):    
    """Gracefully shuts down the server."""
    app.logger.info("Shutdown request received. Cleaning up...")
    
    await app.clients.reset_motors()

    # Stop fault poller task if running
    if hasattr(app, 'monitor_task') and app.monitor_task:
        app.monitor_task.cancel()
        await asyncio.sleep(1)  # Allow task to cancel properly

    # Cleanup Modbus clients
    if hasattr(app, 'clients') and app.clients:
        app.clients.cleanup()

    # Cleanup modules
    if hasattr(app, 'module_manager') and app.module_manager:
        app.module_manager.cleanup_all()

    app.logger.info("Cleanup complete. Shutting down server.")
    os._exit(0)


def cleanup(app):
    app.logger.info("cleanup function executed!")
    app.module_manager.cleanup_all()
    if app.clients is not None:
        app.clients.cleanup()

    sys.exit(1)

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

async def get_modbuscntrl_val(clients, config):
        """
        Gets the current revolutions of both motors and calculates with linear interpolation
        the percentile where they are in the current max_rev - min_rev range.
        After that we multiply it with the maxium modbuscntrl val (10k)
        """
        result = await clients.get_current_revs()
        if result is False:
            cleanup()

        pfeedback_client_left, pfeedback_client_right = result

        revs_left = convert_to_revs(pfeedback_client_left)
        revs_right = convert_to_revs(pfeedback_client_right)

        ## Percentile = x - pos_min / (pos_max - pos_min)
        POS_MIN_REVS = 0.393698024
        POS_MAX_REVS = 28.937007874015748031496062992126
        modbus_percentile_left = (revs_left - POS_MIN_REVS) / (POS_MAX_REVS - POS_MIN_REVS)
        modbus_percentile_right = (revs_right - POS_MIN_REVS) / (POS_MAX_REVS - POS_MIN_REVS)
        modbus_percentile_left = max(0, min(modbus_percentile_left, 1))
        modbus_percentile_right = max(0, min(modbus_percentile_right, 1))

        position_client_left = math.floor(modbus_percentile_left * config.MODBUSCTRL_MAX)
        position_client_right = math.floor(modbus_percentile_right * config.MODBUSCTRL_MAX)

        return position_client_left, position_client_right


def convert_to_revs(pfeedback):
    decimal = pfeedback.registers[0] / 65535
    num = pfeedback.registers[1]
    return num + decimal

async def init(app):
    try:
        logger = setup_logging("server", "server.log")
        module_manager = ModuleManager(logger)
        config = handle_launch_params()
        clients = ModbusClients(config=config, logger=logger)

        # fault_poller_pid = module_manager.launch_module("fault_poller")
        # app.monitor_task = asyncio.create_task(monitor_fault_poller(app))

        # Connect to both drivers
        connected = await clients.connect() 

        if not connected:  
            sys.exit(1)

        app.app_config = config
        app.logger = logger
        
        app.module_manager = module_manager
        app.is_process_done = True
        # app.fault_poller_pid = fault_poller_pid
        app.clients = clients

        atexit.register(lambda: cleanup(app))
        
        await clients.set_host_command_mode(0)
        ### TODO - posita myöhemmin kun fault pollerin toimimaan
        await clients.set_ieg_mode(65535)
        homed = await clients.home()
        if homed: 
            ## Prepare motor parameters for operation
            ### If any of them are unsuccesful -> cleanup and shutdown

            ### MAX POSITION LIMITS FOR BOTH MOTORS | 147 mm
            if not await clients.set_analog_pos_max(61406, 28):
                cleanup()

            ### MIN POSITION LIMITS FOR BOTH MOTORS || 2 mm
            if not await clients.set_analog_pos_min(25801, 0):
                cleanup()

            ### Velocity whole number is in 8.8 where decimal is in little endian format,
            ### meaning smaller bits come first, so 1 rev would be 2^8
            (velocity_whole, velocity_decimal) = convert_vel_rpm_revs(config.VEL)
            if not await clients.set_analog_vel_max(velocity_decimal, velocity_whole):
                cleanup()

            ### UACC32 whole number split in 12.4 format
            (acc_whole, acc_decimal) =convert_acc_rpm_revs(config.ACC)
            if not await clients.set_analog_acc_max(acc_decimal, acc_whole):
                cleanup()

            ## Analog input channel set to use modbusctrl (2)
            if not await clients.set_analog_input_channel(2):
                cleanup()

            (position_client_left, position_client_right) = await get_modbuscntrl_val(clients, config)

            # modbus cntrl 0-10k
            if not await clients.set_analog_modbus_cntrl((position_client_left, position_client_right)):
                cleanup()

            # TODO Ipeak pitää varmistaa vielä onhan 128 arvo = 1 Ampeeri 
            # await clients.client_right.write_register(address=config.IPEAK,value=640,slave=config.SLAVE_ID)
            # await clients.client_left.write_register(address=config.IPEAK,value=640,slave=config.SLAVE_ID)

            # # Finally - Ready for operation
            if not await clients.set_host_command_mode(config.ANALOG_POSITION_MODE):
                cleanup()

            # Enable motors
            if not await clients.set_ieg_mode(2):
                cleanup()
        

    except Exception as e:
        logger.error(f"Initialization failed: {e}")


async def create_app():
    app = Quart(__name__)
    await init(app)

    @app.route("/write", methods=['get'])
    async def write():
        pitch = request.args.get('pitch')
        roll = request.args.get('roll') 
        asd = request.args.get('asd')   
        MODBUSCTRL_MAX = app.app_config.MODBUSCTRL_MAX

        if (asd == "q"):
            a = 10
            await app.clients.client_right.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=MODBUSCTRL_MAX, slave=app.app_config.SLAVE_ID)
            await app.clients.client_left.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=MODBUSCTRL_MAX, slave=app.app_config.SLAVE_ID)



        if (pitch == "+"): # forward
            (position_client_left, position_client_right) = await get_modbuscntrl_val(app.clients, app.app_config)

            position_client_left = math.floor(position_client_left + (MODBUSCTRL_MAX * 0.15)) 
            position_client_right = math.floor(position_client_right + (MODBUSCTRL_MAX* 0.15)) 

            position_client_right = min(MODBUSCTRL_MAX, position_client_right)
            position_client_left = min(MODBUSCTRL_MAX, position_client_left)

            await app.clients.client_right.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_right, slave=app.app_config.SLAVE_ID)
            await app.clients.client_left.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_left, slave=app.app_config.SLAVE_ID)

        elif (pitch == "-"): #backward
            (position_client_left, position_client_right) = await get_modbuscntrl_val(app.clients, app.app_config)

            position_client_left = math.floor(position_client_left - (MODBUSCTRL_MAX* 0.15)) 
            position_client_right = math.floor(position_client_right - (MODBUSCTRL_MAX* 0.15)) 

            position_client_right = max(0, position_client_right)
            position_client_left = max(0, position_client_left)

            await app.clients.client_right.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_right, slave=app.app_config.SLAVE_ID)
            await app.clients.client_left.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_left, slave=app.app_config.SLAVE_ID)
        elif (roll == "-"):# left
            (position_client_left, position_client_right) = await get_modbuscntrl_val(app.clients, app.app_config)
            position_client_left = math.floor(position_client_left - (MODBUSCTRL_MAX* 0.08)) 
            position_client_right = math.floor(position_client_right + (MODBUSCTRL_MAX* 0.08)) 

            position_client_right = min(MODBUSCTRL_MAX, position_client_right)
            position_client_left = max(0, position_client_left)

            await app.clients.client_right.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_right, slave=app.app_config.SLAVE_ID)
            await app.clients.client_left.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_left, slave=app.app_config.SLAVE_ID)
        elif (roll == "+"):
            (position_client_left, position_client_right) = await get_modbuscntrl_val(app.clients, app.app_config)
            position_client_left = math.floor(position_client_left + (MODBUSCTRL_MAX* 0.10)) 
            position_client_right = math.floor(position_client_right - (MODBUSCTRL_MAX* 0.10)) 

            position_client_left = min(MODBUSCTRL_MAX, position_client_left)
            position_client_right = max(0, position_client_right)

            await app.clients.client_right.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_right, slave=app.app_config.SLAVE_ID)
            await app.clients.client_left.write_register(address=app.app_config.ANALOG_MODBUS_CNTRL, value=position_client_left, slave=app.app_config.SLAVE_ID)
        else:
            app.logger.error("Wrong parameter use direction (l | r)")
    
    @app.route('/shutdown', methods=['get'])
    async def shutdown():
        """Shuts down the server when called."""
        app.logger.info("Shutdown request received.")
        await shutdown_test(app)

    @app.route('/stop', methods=['get'])
    async def stop_motors():
        try:
            success = await app.clients.stop()
            if not success:
                pass # do something crazy :O
        except Exception as e:
            app.logger.error("Failed to stop motors?") # Mitäs sitten :D

    @app.route('/asd')
    async def asd():
        print("terve")

    return app
if __name__ == '__main__':
    async def run_app():
        app = await create_app()
        await app.run_task(port=app.app_config.WEB_SERVER_PORT)

    asyncio.run(run_app())
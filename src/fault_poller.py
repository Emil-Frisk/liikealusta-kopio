from pymodbus.client import ModbusTcpClient
import pymodbus.pdu.register_message as pdu_reg
import atexit
from time import sleep
from config import Config
from setup_logging import setup_logging
from ModbusClients import ModbusClients
from launch_params import handle_launch_params
import requests



def main():
    logger = setup_logging("faul_poller", "faul_poller.log")
    config = handle_launch_params()
    clients = ModbusClients(config=config, logger=logger)
    atexit.register(clients.cleanup)

    # for i in range(config.CONNECTION_TRY_COUNT):
    #     if not clients.connect():
    #         logger.error(f"Failed to initialize connections, attempt: {i+1}")
    #         if (i+1 == config.CONNECTION_TRY_COUNT):
    #             logger.error(f"Could not initialize connections for the clients -> exiting")
    #             return

    logger.info(f"Starting polling loop with polling time interval: {config.POLLING_TIME_INTERVAL}")

    try:
        while(True):
            sleep(config.POLLING_TIME_INTERVAL)
            # clients.check_and_reset_tids()
            print("I am pretending to be alive")

            # katso ensin onko moottorissa fault tila
            # jos on katso onko se coms fault
            ## TODO - ota selvää miltä coms fault vastaus näyttää
            # if (clients.check_fault_stauts()):
            #     left_response, right_response = clients.get_recent_fault()
            #     # comms faultti jommassakummassa moottorissa
            #     if (left_response == 10 or right_response == 10): 
            #         # TODO - sammuta moottorit -> lähetä tcp request palvelimelle
            #         a = 10

            # print("Transaction id: " + str(left_response))
            # print("Count: " + str(right_response))
            
    except KeyboardInterrupt:
        logger.info("Polling stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {str(e)}")
    finally:
        clients.cleanup()

if __name__ == "__main__":
    main()
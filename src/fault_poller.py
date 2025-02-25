from pymodbus.client import ModbusTcpClient
import pymodbus.pdu.register_message as pdu_reg
import atexit
from time import sleep
import argparse
import sys
from fault_poller_conf import FaultConfig as Config
from setup_logging import setup_logging
from ModbusClients import ModbusClients

def handle_launch_params():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="port number")
    parser.add_argument("--server_left", type=str, help="left side motor ip")
    parser.add_argument("--server_right", type=str, help="right side motor ip")
    parser.add_argument("--slaveid", type=int, help="drivers slave id")
    parser.add_argument("--hz", type=int, help="polling hz")
    parser.add_argument("--start_tid", type=int, help="start tid")
    parser.add_argument("--end_tid", type=int, help="end tid")

    config = Config()
    config.MODULE_NAME = sys.argv[0]

    args = parser.parse_args()
    if (args.port):
        config.SERVER_PORT = args.port
    if (args.server_left):
        config.SERVER_IP_LEFT = args.server_left
    if (args.server_right):
        config.SERVER_IP_RIGHT = args.server2_right
    if (args.slaveid):
        config.SLAVE_ID = args.slaveid
    if (args.slaveid):
        config.POLLING_HZ = args.hz
    if (args.start_tid):
        config.START_TID = args.start_tid
    if (args.end_tid):
        config.LAST_TID = args.end_tid

    return config

def main():
    logger = setup_logging("fault_poller", "fault_poller.log")
    config = handle_launch_params()
    clients = ModbusClients(config=config, logger=logger)
    atexit.register(clients.cleanup)

    for i in range(config.CONNECTION_TRY_COUNT):
        if not clients.connect():
            logger.error(f"Failed to initialize connections, attempt: {i+1}")
            if (i+1 == config.CONNECTION_TRY_COUNT):
                logger.error(f"Could not initialize connections for the clients -> exiting")
                return

    logger.info(f"Starting polling loop with frequency {config.POLLING_HZ} Hz")

    try:
        while(True):
            sleep(1.0/config.POLLING_HZ) # hz
            clients.check_and_reset_tids()
            left_response, right_response = clients.read_faults()

            ## TODO - ota selvää miltä coms fault vastaus näyttää
            print("Transaction id: " + str(left_response))
            print("Count: " + str(right_response))
    except KeyboardInterrupt:
        logger.info("Polling stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {str(e)}")
    finally:
        clients.cleanup()

if __name__ == "__main__":
    main()
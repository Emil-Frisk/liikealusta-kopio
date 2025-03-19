from pymodbus.client import ModbusTcpClient
import pymodbus.pdu.register_message as pdu_reg
import atexit
from time import sleep
from config import Config
from setup_logging import setup_logging
from ModbusClients import ModbusClients
from launch_params import handle_launch_params
import asyncio

async def main():
    logger = setup_logging("faul_poller", "faul_poller.log")
    config = handle_launch_params()
    clients = ModbusClients(config=config, logger=logger)
    atexit.register(clients.cleanup)

    await clients.connect()
    logger.info(f"Starting polling loop with polling time interval: {config.POLLING_TIME_INTERVAL}")

    try:
        while(True):
            await asyncio.sleep(config.POLLING_TIME_INTERVAL)
            clients.check_and_reset_tids()

            # if (clients.check_fault_stauts()):
            #     left_response, right_response = clients.get_recent_fault()
            #     print("Fault Poller fault status left: " + str(left_response))
            #     print("Fault Poller fault status right" + str(right_response))
            #     # Check that its not a critical fault
            #     if (left_response not in [1, 7, 8] and right_response not in [1, 7, 8]):
            #         await clients.fault_reset()
    except KeyboardInterrupt:
        logger.info("Polling stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {str(e)}")
    finally:
        clients.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
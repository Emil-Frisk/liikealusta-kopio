import atexit
from time import sleep
from config import Config
from setup_logging import setup_logging
from ModbusClients import ModbusClients
from launch_params import handle_launch_params
import asyncio
from utils import is_fault_critical

async def main():
    logger = setup_logging("faul_poller", "faul_poller.log")
    config = handle_launch_params()
    clients = ModbusClients(config=config, logger=logger)

    connected = await clients.connect()
    if (not connected):
        return
        
    logger.info(f"Starting polling loop with polling time interval: {config.POLLING_TIME_INTERVAL}")

    try:
        while(True):
            # await asyncio.sleep(config.POLLING_TIME_INTERVAL)
            await asyncio.sleep(0.5)
            
            # clients.check_and_reset_tids()
            if (await clients.check_fault_stauts()):
                # left_response, right_response = clients.get_recent_fault()
                left_response, right_response = await clients.get_recent_fault()
                print("Fault Poller fault status left: " + str(left_response))
                # Check that its not a critical fault
                if not is_fault_critical(left_response) and not is_fault_critical(right_response):
                    await clients.set_ieg_mode(65535)
                    logger.info("Fault cleared")
                else:
                    logger.error("CRITICAL FAULT DETECTED")
    except KeyboardInterrupt:
        logger.info("Polling stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {str(e)}")
    finally:
        clients.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
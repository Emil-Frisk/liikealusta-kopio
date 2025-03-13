
from pymodbus.client import AsyncModbusTcpClient
from typing import Optional
import pymodbus.exceptions
import requests
from utils import is_nth_bit_on
import asyncio
from pymodbus.exceptions import ConnectionException, ModbusIOException
from time import sleep
from utils import IEG_MODE_bitmask_alternative, IEG_MODE_bitmask_default

class ModbusClients:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client_left: Optional[AsyncModbusTcpClient] = None
        self.client_right: Optional[AsyncModbusTcpClient] = None
        self.max_retries = 10
        self.retry_delay = 0.2

    async def connect(self):
        """
        Establishes connections to both Modbus clients.
        Returns True if both connections are successful, or False if either fails
        and returns None if error
        """
        try:
            self.client_left = AsyncModbusTcpClient(
                host=self.config.SERVER_IP_LEFT,
                port=self.config.SERVER_PORT
            )

            self.client_right = AsyncModbusTcpClient(
                host=self.config.SERVER_IP_RIGHT,
                port=self.config.SERVER_PORT
            )

            left_connected = False
            right_connected = False
            max_attempts = self.config.CONNECTION_TRY_COUNT
            attempt_left = 0
            attempt_right = 0

            while (not left_connected or not right_connected) and \
            (attempt_left_count < max_attempts or attempt_right_count < max_attempts):
                if not left_connected:
                    left_connected = await self.client_left.connect()
                    attempt_left_count += 1
                    if not left_connected:
                         self.logger.debug(f"Left connection attempt {attempt_left} failed")

                if not right_connected:
                    right_connected = await self.client_right.connect()
                    attempt_right_count += 1
                    if not right_connected:
                         self.logger.debug(f"Right connection attempt {attempt_right} failed")

                
            if left_connected and right_connected:
                self.logger.info("Both clients connected succesfully")
                return True
            else: 
                self.logger.warning(f"Connection failed after {max_attempts} attempts. "
                                    f"Left: {left_connected}, right: {right_connected}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error connecting to clients {str(e)}")
            return None

    def check_and_reset_tids(self):
        for client in [self.client_left, self.client_right]:
            if client and client.transaction.next_tid >= self.config.LAST_TID:
                client.transaction.next_tid = self.config.START_TID
                self.logger.debug(f"Reset TID for client")

    async def get_recent_fault(self) -> tuple[Optional[int], Optional[int]]:
        """
        Read fault registers from both clients.
        Returns tuple of (left_fault, right_fault), None if read fails
        """
        try:
            left_response = await self.client_left.read_holding_registers(
                address=self.config.RECENT_FAULT_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = await self.client_right.read_holding_registers(
                address=self.config.RECENT_FAULT_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )

            if left_response.isError() or right_response.isError():
                self.logger.error("Error reading fault register")
                return None, None
            
            return left_response.registers[0], right_response.registers[0]

        except Exception as e:
                self.logger.error(f"Exception reading fault registers: {str(e)}")
                return None, None
        
    async def fault_reset(self, mode = "default"):
        try:
            if not (isinstance(mode, str)):
                raise TypeError(f"Wrong type for the parameter it should be a string")
            
            if (mode.upper() not in ("DEFAULT", "ALTERNATIVE")):
                raise ValueError(f"Invalid mode: {mode}. Expected 'DEFAULT' or 'ALTERNATIVE'.")
            
            # Makes sure bits can be only valid bits that we want to control
            # no matter what you give as a input
            if mode == "DEFAULT":
                value = IEG_MODE_bitmask_default(65535)
            else:
                value = IEG_MODE_bitmask_alternative(65535)

            attempt_count = 0
            max_retries = self.max_retries
            retry_delay = self.retry_delay

            while attempt_count < max_retries:
                responses = await asyncio.gather(
                    self.client_left.write_register(
                    address=self.config.IEG_MODE,
                    value=value,
                    slave=self.config.SLAVE_ID
                ),
                    self.client_right.write_register(
                    address=self.config.IEG_MODE,
                    value=value,
                    slave= self.config.SLAVE_ID
                ),
                return_exceptions=True
                )

                left_response, right_response = responses

                if isinstance(left_response, Exception) or isinstance(right_response, Exception):
                    attempt_count += 1
                    self.logger.error("Exception during trying to do a fault reset")
                    await asyncio.sleep(retry_delay*3)
                    continue

                if left_response.isError() or right_response.isError():
                    attempt_count += 1
                    self.logger.error("Error resetting faults")
                    await asyncio.sleep(retry_delay*3)
                    continue

                return True
            
            return False

        except (ConnectionException, asyncio.exceptions.TimeoutError, ModbusIOException) as e:
            self.logger.error(f"Exception reading fault registers: {str(e)}")
            return False
        
    async def check_fault_stauts(self) -> Optional[bool]:
        """
        Read drive status from both motors.
        Returns true if either one is in fault state
        otherwise false
        or None if it fails
        """
        try:
            result = False

            left_response = await self.client_left.read_holding_registers(
                address=self.config.DRIVER_STATUS_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = await self.client_right.read_holding_registers(
                address=self.config.DRIVER_STATUS_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )

            if left_response.isError() or right_response.isError():
                self.logger.error("Error reading driver status register")
                return None

            # 4th bit 2^4 indicates if motor is in the fault state
            if(is_nth_bit_on(3, left_response.registers[0]) or is_nth_bit_on(3, right_response.registers[0])):
                 result = True
            
            return result

        except Exception as e:
                self.logger.error(f"Exception checking fault status: {str(e)}")
                return None
    
    async def get_vel(self):
        """
        Gets velocity from both registers returns None if error
        """
        try:
            left_response = await  self.client_left.read_holding_registers(
                address=self.config.VFEEDBACK_VELOCITY,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = await self.client_right.read_holding_registers(
                address=self.config.VFEEDBACK_VELOCITY,
                count=1,
                slave=self.config.SLAVE_ID
            )

            if left_response.isError() or right_response.isError():
                self.logger.error("Error reading velocity register")
                return None, None
            
            return left_response.registers[0], right_response.registers[0]

        except Exception as e:
                self.logger.error(f"Exception reading fault registers: {str(e)}")
                return None, None


    async def stop(self):
        """
        Attempts to stop both motors by writing to the IEG_MOTION register.
        Returns True if successful, False if failed after retries.
        """
        attempt_count = 0
        max_retries = self.max_retries
        retry_delay = self.retry_delay

        while attempt_count < max_retries:
            try:
                # Attempt to stop both motors in parallel
                responses = await asyncio.gather(
                    self.client_left.write_register(
                        address=self.config.IEG_MOTION,
                        value=4,
                        slave=self.config.SLAVE_ID
                    ),
                    self.client_right.write_register(
                        address=self.config.IEG_MOTION,
                        value=4,
                        slave=self.config.SLAVE_ID
                    ),
                    return_exceptions=True
                )

                left_response, right_response = responses

                # Check for exceptions in the responses
                if isinstance(left_response, Exception) or isinstance(right_response, Exception):
                    attempt_count += 1
                    self.logger.error(
                        f"Exception during parallel write (attempt {attempt_count}/{max_retries}): "
                        f"Left: {left_response}, Right: {right_response}"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                # Check for Modbus errors in the responses
                if left_response.isError() or right_response.isError():
                    attempt_count += 1
                    self.logger.error(
                        f"Modbus error stopping motors (attempt {attempt_count}/{max_retries}): "
                        f"Left: {left_response}, Right: {right_response}"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                # Success
                self.logger.info("Successfully stopped both motors")
                return True

            except (ConnectionException, asyncio.exceptions.TimeoutError, ModbusIOException) as e:
                attempt_count += 1
                self.logger.error(f"Connection error (attempt {attempt_count}/{max_retries}): {e}")

                # Check if either client is disconnected
                if not self.client_left.connected or not self.client_right.connected:
                    self.logger.info("One or both clients disconnected. Attempting to reconnect...")
                    await self.connect()

                if attempt_count < max_retries:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    self.logger.error("Max retries reached. Failed to stop motors.")
                    return False

            except Exception as e:
                # Log unexpected errors and fail immediately
                self.logger.error(f"Unexpected error while stopping motors: {e}")
                return False

        self.logger.error("Failed to stop motors after maximum retries. Critical failure!")
        return False

    def cleanup(self):
        self.logger.info(f"cleanup function executed at module {self.config.MODULE_NAME}")
        if self.client_left is not None and self.client_right is not None:
            self.client_left.close()
            self.client_right.close()    
            

from pymodbus.client import ModbusTcpClient
from typing import Optional
import requests
from utils import is_nth_bit_on
from time import sleep

class ModbusClients:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client_left: Optional[ModbusTcpClient] = None
        self.client_right: Optional[ModbusTcpClient] = None
        self.max_retries = 5  # Maximum retry attempts
        self.retry_delay = 0.050  # Initial delay in seconds (doubles with each retry)

    def connect(self):
        """
        Establishes connections to both Modbus clients.
        Returns True if both connections are successful.
        """
        
        try:
            self.client_left = ModbusTcpClient(
                self.config.SERVER_IP_LEFT,
                port=self.config.SERVER_PORT
            )

            self.client_right = ModbusTcpClient(
                self.config.SERVER_IP_RIGHT,
                port=self.config.SERVER_PORT
            )

            left_connected = self.client_left.connect()
            right_connected = self.client_left.connect()

            if left_connected and right_connected:
                self.client_left.transaction.next_tid = self.config.startTID
                self.client_right.transaction.next_tid = self.config.startTID
                self.logger.info("Successfully connected to both clients")
                return True
            else:
                self.self.logger.error("Error connecting to both clients")
                return False
            
        except Exception as e:
            self.logger.error(f"Error connecting to clients {str(e)}")
            return False

    def check_and_reset_tids(self):
        for client in [self.client_left, self.client_right]:
            if client and client.transaction.next_tid >= self.config.LAST_TID:
                client.transaction.next_tid = self.config.START_TID
                self.logger.debug(f"Reset TID for client")

    def get_recent_fault(self) -> tuple[Optional[int], Optional[int]]:
        """
        Read fault registers from both clients.
        Returns tuple of (left_fault, right_fault), None if read fails
        """
        try:
            left_response = self.client_left.read_holding_registers(
                address=self.config.RECENT_FAULT_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = self.client_right.read_holding_registers(
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
        
    def check_fault_stauts(self) -> Optional[bool]:
        """
        Read drive status from both motors.
        Returns true if either one is in fault state
        otherwise false
        or None if it fails
        """
        try:
            result = False

            left_response = self.client_left.read_holding_registers(
                address=self.config.DRIVER_STATUS_ADDRESS,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = self.client_right.read_holding_registers(
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
    
    def get_vel(self):
        """
        Gets velocity from both registers returns None if error
        """
        try:
            left_response = self.client_left.read_holding_registers(
                address=self.config.VFEEDBACK_VELOCITY,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = self.client_right.read_holding_registers(
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

    def stop(self):
        
            attempt_count = 0
            while(self.max_retries >= attempt_count):
                try:
                    left_response = self.client_left.write_register( # stop = 4
                        address=self.config.IEG_MOTION,
                        value=4,
                        slave=self.config.SLAVE_ID
                    )
                    right_response = self.client_right.write_register(
                        address=self.config.IEG_MOTION,
                        value=4,
                        slave=self.config.SLAVE_ID
                    )

                    if left_response.isError() or right_response.isError():
                        attempt_count += 1
                        self.logger.error(f"Error stopping motor trying again i: {attempt_count}")
                        sleep(self.retry_delay)
                        continue
                    else:
                        self.logger.info(f"Succesfully stopped both motors")        
                        return

                except Exception as e:
                    retry_count += 1
                    if retry_count < self.max_retries:
                        delay = self.retry_delay * (2 ** retry_count)
                        self.logger.info(f"Retrying in {delay} seconds due to exception...")
                        sleep(delay)
                        continue

                self.logger.error("Failed to stop motors after maximum retries. Critical failure!")
                raise RuntimeError("Unable to stop motors after maximum attempts")
        

    def cleanup(self):
        self.logger.info(f"cleanup function executed at module {self.config.MODULE_NAME}")
        if self.client_left is not None and self.client_right is not None:
            self.client_left.close()
            self.client_right.close()    
            
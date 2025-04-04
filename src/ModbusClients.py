
from pymodbus.client import AsyncModbusTcpClient
from typing import List, Optional, Tuple, Union
from utils import is_nth_bit_on
import asyncio
from pymodbus.exceptions import ConnectionException, ModbusIOException
from time import sleep
import time
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
            max_attempts = 3
            attempt_left = 0
            attempt_right = 0

            while (not left_connected or not right_connected) and \
            (attempt_left < max_attempts or attempt_right < max_attempts):
                if not left_connected:
                    left_connected = await self.client_left.connect()
                    attempt_left += 1
                    if not left_connected:
                         self.logger.debug(f"Left connection attempt {attempt_left} failed")

                if not right_connected:
                    right_connected = await self.client_right.connect()
                    attempt_right += 1
                    if not right_connected:
                         self.logger.debug(f"Right connection attempt {attempt_right} failed")
                
            if left_connected and right_connected:
                self.logger.info("Both clients connected succesfully")

                # if "fault_poller.py" in self.config.MODULE_NAME:
                #     self.client_left.ctx.next_tid = self.config.START_TID
                #     self.client_right.ctx.next_tid = self.config.START_TID

                return True
            else: 
                self.logger.warning(f"Connection failed after {max_attempts} attempts. "
                                    f"Left: {left_connected}, right: {right_connected}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error connecting to clients {str(e)}")
            return None

    # def check_and_reset_tids(self):
    #     for client in [self.client_left, self.client_right]:
    #         if client and client.ctx.next_tid >= self.config.LAST_TID:
    #             client.ctx.next_tid = self.config.START_TID
    #             self.logger.debug(f"Reset TID for client")

    async def reset_motors(self):
        """ 
        Removes all temporary settings from both motors
        and goes back to default ones
        """
        await self.client_left.write_register(address=4001, value=1)
        await self.client_right.write_register(address=4001, value=1)

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
                address=self.config.OEG_STATUS,
                count=1,
                slave=self.config.SLAVE_ID
            )
            right_response = await self.client_right.read_holding_registers(
                address=self.config.OEG_STATUS,
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

    async def home(self):
        try:
            attempt_left = 0
            attempt_right = 0
            success_right = False
            success_left = False
            max_retries = self.max_retries
            
            response_left = await self.client_right.write_register(address=self.config.IEG_MOTION,
                                value=0,
                                slave=self.config.SLAVE_ID)
            response_right = await self.client_left.write_register(address=self.config.IEG_MOTION,
                                    value=0,
                                    slave=self.config.SLAVE_ID)

            while max_retries > attempt_left and max_retries > attempt_right:
                if not success_left:
                    response_left = await self.client_right.write_register(address=self.config.IEG_MOTION,
                                            value=256,
                                            slave=self.config.SLAVE_ID)
                if not success_right:
                    response_right = await self.client_left.write_register(address=self.config.IEG_MOTION,
                                            value=256,
                                            slave=self.config.SLAVE_ID)
            
                if response_left.isError():
                    attempt_left += 1
                    self.logger.error(f"Failed to initiate homing command on left. Attempt {attempt_left}")
                else:
                    success_left = True

                if response_right.isError():
                    attempt_right += 1
                    self.logger.error(f"Failed to initiate homing command on right motor. Attempt {attempt_right}")
                else:
                    success_right = True
                
                if success_left and success_right:
                    break
            
            if not success_left or not success_right:
                self.logger.error(f"Failed to initiate homing command on both motors. Left: {success_left} | right: Left: {success_right}")
                return False

            ### homing order was success for both motos make a poller coroutine to poll when the homing is done.
            #Checks if both actuators are homed or not. Returns True when homed.
            homing_max_duration = 30
            start_time = time.time()
            elapsed_time = 0
            while elapsed_time <= homing_max_duration:
                OEG_STATUS_right = await self.client_right.read_holding_registers(address=self.config.OEG_STATUS,
                                    count=1,
                                    slave=self.config.SLAVE_ID)

                OEG_STATUS_left = await self.client_left.read_holding_registers(address=self.config.OEG_STATUS,
                                        count=1,
                                        slave=self.config.SLAVE_ID)
                
                if OEG_STATUS_right.isError() or OEG_STATUS_left.isError():
                    self.logger.error(f"Unexpected error while reading OEG_STATUS registers: ")
                    await asyncio.sleep(0.2)
                    continue
                
                ishomed_right = is_nth_bit_on(1, OEG_STATUS_right.registers[0])
                ishomed_left = is_nth_bit_on(1, OEG_STATUS_left.registers[0])

                # Success
                if ishomed_right and ishomed_left:
                    self.logger.info(f"Both motors homes successfully:")
                    return True
                
                await asyncio.sleep(0.2)
                elapsed_time = time.time() - start_time
            
            self.logger.error(f"Failed to home both motors within the time limit of: {homing_max_duration}")
            return False


        except Exception as e:
            self.logger.error(f"Unexpected error while homing motors: {e}")
            return False
    
    async def set_analog_pos_max(self, decimal: int, whole: int) -> bool:
        """
        Sets the analog position maximum for both motors.
        Args:
            decimal (int): The decimal part of the position limit.
            whole (int): The whole number part of the position limit.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            values = [decimal, whole]

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_registers(
                        address=self.config.ANALOG_POSITION_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog position max on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog position max on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_registers(
                        address=self.config.ANALOG_POSITION_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog position max on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog position max on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog position max on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog position max on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog position max: {str(e)}")
            return False
    
    async def set_analog_pos_min(self, decimal: int, whole: int) -> bool:
        """
        Sets the analog position minium for both motors.
        Args:
            decimal (int): The decimal part of the position limit.
            whole (int): The whole number part of the position limit.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            values = [decimal, whole]

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_registers(
                        address=self.config.ANALOG_POSITION_MINIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog position min on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog position min on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_registers(
                        address=self.config.ANALOG_POSITION_MINIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog position min on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog position min on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog position min on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog position min on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog position min: {str(e)}")
            return False
    
    async def set_analog_vel_max(self, decimal: int, whole: int) -> bool:
        """
        Sets the analog velocity maxium for both motors.
        Args:
            decimal (int): The decimal part of the velocity limit.
            whole (int): The whole number part of the velocity limit.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            values = [decimal, whole]

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_registers(
                        address=self.config.ANALOG_VEL_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog velocity max on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog velocity max on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_registers(
                        address=self.config.ANALOG_VEL_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog velocity max on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog velocity max on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog velocity max on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog velocity max on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog velocity max: {str(e)}")
            return False
    
    async def set_analog_acc_max(self, decimal: int, whole: int) -> bool:
        """
        Sets the analog acceleration maxium for both motors.
        Args:
            decimal (int): The decimal part of the acceleration limit.
            whole (int): The whole number part of the acceleration limit.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            values = [decimal, whole]

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_registers(
                        address=self.config.ANALOG_ACCELERATION_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog acceleration max on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog acceleration max on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_registers(
                        address=self.config.ANALOG_ACCELERATION_MAXIMUM,
                        values=values,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog acceleration max on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog acceleration max on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog acceleration max on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog acceleration max on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog acceleration max: {str(e)}")
            return False
    
    async def set_analog_input_channel(self, value: int) -> bool:
        """
        Sets the analog input channel for both motors.
        Args:
            value (int): The value for the analog input channel.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_register(
                        address=self.config.ANALOG_INPUT_CHANNEL,
                        value=value,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog input channel on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog input channel on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_register(
                        address=self.config.ANALOG_INPUT_CHANNEL,
                        value=value,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog input channel on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog input channel on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog input channel on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog input channel on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog input channel: {str(e)}")
            return False
        
    async def get_current_revs(self) ->  Union[Tuple[List[int], List[int]], bool]:
        """
        Gets the current REVS for both motors
        Returns:
             A tuple of (response_left, response_right), where each response is a list of two integers:
            - response_left: [decimal_part, whole_part] for the left motor
            - response_right: [decimal_part, whole_part] for the right motor
            Returns False if the operation is not successful.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.read_holding_registers(
                        address=self.config.PFEEDBACK_POSITION,
                        count=2,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to read current REVS on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully read current REVS on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.read_holding_registers(
                        address=self.config.PFEEDBACK_POSITION,
                        count=2,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to read current REVS on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully read current REVS on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to read current REVS on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully read current REVS on both motors")
            return (response_left, response_right)

        except Exception as e:
            self.logger.error(f"Unexpected error while reading motor REVS: {str(e)}")
            return False
    
    async def set_analog_modbus_cntrl(self, values: Tuple[int, int]) -> bool:
        """
        Sets the analog input Modbus control value for both motors,
        where 0 makes the motor go to the analog_pos_min position
        and 10,000 makes the motor go to the analog_pos_max position.
        Args:
            values: A tuple of (value_left, value_right) where each value is an integer
                    between 0 and 10,000 representing the control value for the left and right motors.
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor
            value_left, value_right = values

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_register(
                        address=self.config.ANALOG_MODBUS_CNTRL,
                        value=value_left,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set analog modbuscntrl value on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set analog modbuscntrl value on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_register(
                        address=self.config.ANALOG_MODBUS_CNTRL,
                        value=value_right,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set analog modbuscntrl value on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set analog modbuscntrl value on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set analog modbuscntrl value on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set analog modbuscntrl value on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting analog modbuscntrl value: {str(e)}")
            return False
    
    async def set_host_command_mode(self, value: int) -> bool:
        """
        Sets both of the motors host command mode to value
        Args:
            value: 
            OPMODE MAP
                0: disabled
                1: digital inputs
                2: analog position
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_register(
                        address=self.config.COMMAND_MODE,
                        value=value,
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set host command mode value on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set host command mode value on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_register(
                        address=self.config.COMMAND_MODE,
                        value=value,
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set host command mode value on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set host command mode value on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set host command mode value on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set host command mode value on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting host command mode value: {str(e)}")
            return False
        
    async def set_ieg_mode(self, value: int) -> bool:
        """
        Sets IEG_MODE bits
        !!! IMPORTANT NOTE !!! 
        DO NOT EVER ACTIVATE ALL BITS IT WILL DEFINE NEW HOME AND THE WHOLE SYSTEM
        WILL BRAKE, IT WILL ALSO DISABLE THE MOTORS BREAKS MAKE SURE TO USE
        BIT MAKS DEFINED IN THE UTILS (IEG_MODE_bitmask_default) and (IEG_MODE_bitmask_alternative)
        THESE BITMASKS WILL MAKE SURE DANGEROUS BITS WILL NEVER BE ON EVEN IF YOU USE MAX UINT32 VALUE
        Args:
            value: 
            bit map
                0: enable momentary
                1: enable maintained
                7: alt mode
                15: reset fault
        Returns:
            bool: True if successful for both motors, False otherwise.
        """
        try:
            attempt_left = 0
            attempt_right = 0
            success_left = False
            success_right = False
            max_retries = 3  # 3 retries for each motor

            while max_retries > attempt_left and max_retries > attempt_right:
                # Write to left motor if not yet successful
                if not success_left:
                    response_left = await self.client_left.write_register(
                        address=self.config.IEG_MODE,
                        value=IEG_MODE_bitmask_default(value),
                        slave=self.config.SLAVE_ID
                    )
                    if response_left.isError():
                        attempt_left += 1
                        self.logger.error(f"Failed to set ieg mode value on left motor. Attempt {attempt_left}/{max_retries}")
                    else:
                        success_left = True
                        self.logger.info("Successfully set ieg mode value on left motor")

                # Write to right motor if not yet successful
                if not success_right:
                    response_right = await self.client_right.write_register(
                        address=self.config.IEG_MODE,
                        value=IEG_MODE_bitmask_default(value),
                        slave=self.config.SLAVE_ID
                    )
                    if response_right.isError():
                        attempt_right += 1
                        self.logger.error(f"Failed to set ieg mode value on right motor. Attempt {attempt_right}/{max_retries}")
                    else:
                        success_right = True
                        self.logger.info("Successfully set ieg mode value on right motor")

                # Break if both are successful
                if success_left and success_right:
                    break

                # Delay between retries
                await asyncio.sleep(self.retry_delay)

            if not success_left or not success_right:
                self.logger.error(f"Failed to set ieg mode mode value on both motors. Left: {success_left}, Right: {success_right}")
                return False

            self.logger.info("Successfully set ieg mode mode value on both motors")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error while setting ieg mode value: {str(e)}")
            return False


                    
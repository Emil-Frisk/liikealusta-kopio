
from pymodbus.client import ModbusTcpClient
from typing import Optional

class ModbusClients:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client_left: Optional[ModbusTcpClient] = None
        self.client_right: Optional[ModbusTcpClient] = None

    def is_4th_bit_on(number):
             # tekee bittiarvon 00001000 | bitit lasketaan 0 joten 3 on 4's bit
             mask = 1 << 3
             # tekee bitwise AND vertailun palauttaa 8 binäärimuodossa vain jos oikea bitti on päällä
             return (number & mask) != 0

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
        Returns boolean or None if it fails
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

            if(self.is_4th_bit_on(left_response.registers[0]) or self.is_4th_bit_on(right_response.registers[0])):
                 result = True
            
            return result

        except Exception as e:
                self.logger.error(f"Exception checking fault status: {str(e)}")
                return None
        
    def cleanup(self):
    # TODO - ilmoita serverille johonkin endpoittiin
    # että fault poller on sammunut ja se yrittää käynnistää
    # sen uudelleen automaattisesti. (tämän moduulin ei pitäisi sammua
    # jos servu on vielä käynnissä)
        if (self.config.MODULE_NAME == "fault_poller.py"):
            print("cleanup func executed!")
            self.client_left.close()
            self.client_right.close()
            # ilmoita servulle
            
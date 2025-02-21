
from pymodbus.client import ModbusTcpClient
from typing import Optional

class ModbusClients:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client_left: Optional[ModbusTcpClient] = None
        self.client_right: Optional[ModbusTcpClient] = None

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

    def read_faults(self) -> tuple[Optional[int], Optional[int]]:
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
        
    def cleanup(self):
    # TODO - ilmoita serverille johonkin endpoittiin
    # että fault poller on sammunut ja se yrittää käynnistää
    # sen uudelleen automaattisesti. (tämän moduulin ei pitäisi sammua
    # jos servu on vielä käynnissä)
        if (self.config.MODULE_NAME == "fault_poller.py"):
            print("cleanup func executed!")
            self.client_left.close()
            self.client_right.close()
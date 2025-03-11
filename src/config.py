from dataclasses import dataclass

@dataclass
class Config:
    RECENT_FAULT_ADDRESS: int = 846 #Coms bit 10 -> 2^10
    DRIVER_STATUS_ADDRESS: int = 104
    IEG_MOTION: int = 4317 # stop 2^2
    VFEEDBACK_VELOCITY: int = 361
    SERVER_IP_LEFT: str = '192.168.0.211'  
    SERVER_IP_RIGHT: str = '192.168.0.212'
    POS_UPDATE_HZ: int = 1
    SERVER_PORT: int = 502  
    SLAVE_ID: int = 1
    POLLING_TIME_INTERVAL: float = 5.0
    START_TID: int = 10001 # first TID will be startTID + 1
    LAST_TID: int = 20000
    CONNECTION_TRY_COUNT = 5
    WEB_SERVER_PORT: int = 5001
    MODULE_NAME = None
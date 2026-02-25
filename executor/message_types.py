from enum import Enum


class MessageType(str, Enum):
    """
    Message types that a bridge can publish.
    """
    IMU = "imu"
    DWM = "dwm"
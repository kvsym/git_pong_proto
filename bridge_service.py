import time
from imu_thread_test import IMUSensor
from dwm_thread_test import DWMSensor


class BridgeService:
    def __init__(self):
        self.imu = IMUSensor()
        self.dwm = DWMSensor()

    def start(self):
        self.imu.start()
        self.dwm.start()

    def snapshot(self):
        return {
            "imu": self.imu.latest_quat,
            "dwm": self.dwm.latest_position
        }


if __name__ == "__main__":
    bridge = BridgeService()
    bridge.start()

    try:
        while True:
            data = bridge.snapshot()
            print("[BRIDGE]", data)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
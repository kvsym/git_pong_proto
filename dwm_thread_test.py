import threading
import time
from serial import Serial
import dwm1001


class DWMSensor(threading.Thread):
    def __init__(self, port="/dev/ttyACM0"):
        super().__init__(daemon=True)
        self.latest_position = None
        self.running = True

        self.serial = Serial(port, baudrate=115200, timeout=1)
        self.tag = dwm1001.ActiveTag(self.serial)
        self.tag.start_position_reporting()

    def run(self):
        print("[DWM] Thread started")
        while self.running:
            try:
                pos = self.tag.position
                if pos:
                    self.latest_position = pos
            except Exception:
                pass
            time.sleep(0.1)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    dwm = DWMSensor()
    dwm.start()

    try:
        while True:
            print("[MAIN] Latest position:", dwm.latest_position)
            time.sleep(1)
    except KeyboardInterrupt:
        dwm.stop()
import threading
import time
import board
import busio
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR


class IMUSensor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.latest_quat = None
        self.running = True

        i2c = busio.I2C(board.SCL, board.SDA)
        self.bno = BNO08X_I2C(i2c)
        self.bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

    def run(self):
        print("[IMU] Thread started")
        while self.running:
            try:
                quat = self.bno.quaternion
                if quat:
                    self.latest_quat = quat
            except Exception as e:
                print("[IMU] Error:", e)
            time.sleep(0.05)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    imu = IMUSensor()
    imu.start()

    try:
        while True:
            print("[MAIN] Latest quat:", imu.latest_quat)
            time.sleep(1)
    except KeyboardInterrupt:
        imu.stop()
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from executor.constants import IMU_POLL_SEC, BRIDGE_PRINT_SEC
from executor.shared_state import SharedState


def imu_worker(stop: Event, state: SharedState) -> None:
    import board
    import busio
    from adafruit_bno08x.i2c import BNO08X_I2C
    from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
    """
    Background worker function for IMU.

    - Initializes the BNO085 IMU
    - Continuously reads quaternion data
    - Stores latest orientation in SharedState
    - Stops cleanly when stop Event is set
    """
    print("[IMU] Initializing...")
    i2c = busio.I2C(board.SCL, board.SDA)
    bno = BNO08X_I2C(i2c)
    bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
    print("[IMU] Worker started")

    while not stop.is_set():
        try:
            quat = bno.quaternion
            if quat:
                state.set_imu_quat(quat)
        except Exception as e:
            print(f"[IMU] Error: {e}")
        time.sleep(IMU_POLL_SEC)

    print("[IMU] Worker stopping")


def main() -> None:
    stop = Event()
    state = SharedState(_lock=Lock())

    with ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(imu_worker, stop, state)

        try:
            while True:
                snap = state.snapshot()
                print("[MAIN] Latest quat:", snap["imu_quat"])
                time.sleep(BRIDGE_PRINT_SEC)
        except KeyboardInterrupt:
            print("\n[MAIN] Stopping...")
            stop.set()


if __name__ == "__main__":
    main()
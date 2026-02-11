# task_executor_loop.py
import time
from executor.constants import TASK_PERIOD_SEC, STABLE_W_THRESHOLD
from executor.bridge_executor_service import BridgeService


def main() -> None:
    """
    Task loop that consumes sensor data and makes decisions.

    - Periodically reads BridgeService snapshot
    - Evaluates IMU orientation
    - Decides whether to trigger actuators
    """
    bridge = BridgeService()
    bridge.start()

    try:
        while True:
            snap = bridge.snapshot()
            quat = snap["imu_quat"]

            if quat:
                i, j, k, w = quat
                if w >= STABLE_W_THRESHOLD:
                    print("[TASK] Stable orientation (w>=threshold)")
                else:
                    print("[TASK] Orientation changed -> would trigger actuator")

            # you can also read DWM position here:
            # pos = snap["dwm_pos"]

            time.sleep(TASK_PERIOD_SEC)

    except KeyboardInterrupt:
        print("\n[TASK] Shutting down...")
        bridge.shutdown()


if __name__ == "__main__":
    main()

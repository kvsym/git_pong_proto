import time
from bridge_service import BridgeService


class Task:
    def __init__(self, bridge):
        self.bridge = bridge

    def execute(self):
        state = self.bridge.snapshot()
        imu = state["imu"]

        if imu:
            _, _, _, w = imu
            if w > 0.9:
                print("[TASK] Stable orientation → do nothing")
            else:
                print("[TASK] Orientation changed → trigger actuator")


if __name__ == "__main__":
    bridge = BridgeService()
    bridge.start()

    task = Task(bridge)

    try:
        while True:
            task.execute()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from executor.constants import BRIDGE_PRINT_SEC, DWM_DEFAULT_PORT
from executor.shared_state import SharedState
from executor.imu_executor_test import imu_worker
from executor.dwm_executor_test import dwm_worker


class BridgeService:
    """
    Bridge service that manages all sensor workers.

    Responsibilities:
    - Start IMU + DWM workers
    - Own the ThreadPoolExecutor
    - Provide unified snapshot API
    - Handle clean shutdown
    """
    def __init__(self):
        self.stop = Event()
        self.state = SharedState(_lock=Lock())
        self.executor = ThreadPoolExecutor(max_workers=2)

    def start(self) -> None:
        """
        Launch all sensor workers.

        Each worker runs in its own executor thread.
        """
        self.executor.submit(imu_worker, self.stop, self.state)
        self.executor.submit(dwm_worker, self.stop, self.state, DWM_DEFAULT_PORT)

    def snapshot(self) -> dict:
        """
        Return a thread-safe snapshot of all sensor data.

        Used by:
        - Tasks
        - (Zenoh)
        - (Logging)
        """
        return self.state.snapshot()

    def shutdown(self) -> None:
        self.stop.set()
        self.executor.shutdown(wait=True)


def main() -> None:
    bridge = BridgeService()
    bridge.start()

    try:
        while True:
            print("[BRIDGE] Snapshot:", bridge.snapshot())
            time.sleep(BRIDGE_PRINT_SEC)
    except KeyboardInterrupt:
        print("\n[BRIDGE] Shutting down...")
        bridge.shutdown()


if __name__ == "__main__":
    main()

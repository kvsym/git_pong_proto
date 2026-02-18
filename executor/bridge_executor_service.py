import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from typing import Optional
import zenoh
import json

from executor.constants import (
    ZENOH_ENDPOINT,
    ZENOH_KEY_IMU,
    ZENOH_KEY_DWM,
    PUBLISH_PERIOD_SEC,
    DWM_DEFAULT_PORT,
)

from executor.shared_state import SharedState
from executor.imu_executor_test import imu_worker
from executor.dwm_executor_test import dwm_worker


class BridgeService:
    """
    Bridge:
    - Owns SharedState ("blackboard)
    - Owns Zenoh session
    - Starts sensor workers (IMU, DWM)
    - Runs a publish loop that reads SharedState and publishes to Zenoh topics
    """
    def __init__(self, dwm_port: str = DWM_DEFAULT_PORT, enable_dwm: bool = True, enable_imu: bool = True):
        self.stop = Event()
        self.state = SharedState(_lock=Lock())
        self.dwm_port = dwm_port
        self.enable_dwm = enable_dwm
        self.enable_imu = enable_imu

        self.executor: Optional[ThreadPoolExecutor] = None
        self.z: Optional[zenoh.Session] = None

    def create_bridge(self) -> None:
        """
        Creates the bridge:
        - Opens Zenoh Session
        - Starts worker threads and publisher loop in a ThreadPoolExecutor
        """
        print(f"[BRIDGE] Opening Zenoh session to {ZENOH_ENDPOINT}...")
        config = zenoh.Config()
        config.insert_json5("connect/endpoints", f'["{ZENOH_ENDPOINT}"]')
        self.z = zenoh.open(config)
        print("[BRIDGE] Zenoh session opened")

        self.executor = ThreadPoolExecutor(max_workers=4)

        # Start sensors
        if self.enable_imu:
            self.executor.submit(imu_worker, self.stop, self.state)
        if self.enable_dwm:
            self.executor.submit(dwm_worker, self.stop, self.state, self.dwm_port)

        # Start publisher loop
        self.executor.submit(self._publisher_loop)

        print("[BRIDGE] Bridge created (sensors + publisher running)")

    def close_bridge(self) -> None:
        """
        Closes the bridge:
        - Signals stop to all workers
        - Shuts down executor
        - Closes Zenoh session
        """
        print("[BRIDGE] Closing...")
        self.stop.set()

        if self.executor:
            self.executor.shutdown(wait=True)

        if self.z:
            try:
                self.z.close()
            except Exception:
                pass

        print("[BRIDGE] Closed")
    def _publisher_loop(self) -> None:
        """
        Periodic publish loop:
        - Reads SharedState snapshot
        - Publishes IMU and DWM values (if present) to Zenoh
        - Runs at PUBLISH_PERIOD_SEC (0.1s in your diagram)
        """
        assert self.z is not None

        print(f"[BRIDGE] Publisher loop started (period={PUBLISH_PERIOD_SEC}s)")
        while not self.stop.is_set():
            snap = self.state.snapshot()

            # Publish IMU
            imu = snap["imu_quat"]
            if imu is not None:
                payload = json.dumps({
                    "ts": snap["imu_ts"],
                    "quat": {"i": imu[0], "j": imu[1], "k": imu[2], "w": imu[3]},
                }).encode()
                self.z.put(ZENOH_KEY_IMU, payload)

            # Publish DWM
            pos = snap["dwm_pos"]
            if pos is not None:
                data = {"ts": snap["dwm_ts"]}
                for name in ("x_m", "y_m", "z_m", "x", "y", "z"):
                    if hasattr(pos, name):
                        data[name] = float(getattr(pos, name))
                if len(data) == 1:
                    data["raw"] = str(pos)

                self.z.put(ZENOH_KEY_DWM, json.dumps(data).encode())

            time.sleep(PUBLISH_PERIOD_SEC)

        print("[BRIDGE] Publisher loop stopped")

    # def start(self) -> None:
    #     """
    #     Launch all sensor workers.

    #     Each worker runs in its own executor thread.
    #     """
    #     self.executor.submit(imu_worker, self.stop, self.state)
    #     self.executor.submit(dwm_worker, self.stop, self.state, DWM_DEFAULT_PORT)

    # def snapshot(self) -> dict:
    #     """
    #     Return a thread-safe snapshot of all sensor data.

    #     Used by:
    #     - Tasks
    #     - (Zenoh)
    #     - (Logging)
    #     """
    #     return self.state.snapshot()

    # def shutdown(self) -> None:
    #     self.stop.set()
    #     self.executor.shutdown(wait=True)
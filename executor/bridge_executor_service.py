import time
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Event, Lock
from typing import Dict, Optional
from dataclasses import dataclass
import zenoh
import json
import uuid

from executor.constants import (
    ZENOH_ENDPOINT,
    PUBLISH_PERIOD_SEC,
    DWM_DEFAULT_PORT,
)

from executor.shared_state import SharedState
from executor.message_types import MessageType
from executor.imu_executor_test import imu_worker
from executor.dwm_executor_test import dwm_worker

@dataclass
class BridgeHandle:
    """
    Tracks one running bridge publisher task.
    
    - outbound_topic: where we publish in Zenoh
    - message_type: what data we publish from SharedState
    - stop: event to request shutdown
    - future: the executor task future (for debugging / status)
    """
    outbound_topic: str
    message_type: MessageType
    stop: Event
    future: Future

class BridgeManager:
    """
    Owns:
    - One Zenoh session (shared by all bridges)
    - One ThreadPoolExecutor (shared by all sensors+bridges)
    - One SharedState blackboard

    Provides:
    - start_sensors(): submit sensor tasks
    - create_bridge(outbound_topic, message_type): submit publisher task
    - close_bridge(bridge_id): stop just that publisher task
    - shutdown(): stop everything cleanly
    """

    def __init__(self, *, max_workers: int = 6):
        self.state = SharedState(_lock=Lock())

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._zenoh = self._open_zenoh_session()

        self._sensor_stop = Event()
        self._sensors_started = False

        self._bridges: Dict[str, BridgeHandle] = {}
    
    def _open_zenoh_session(self) -> zenoh.Session:
        """Create and return a Zenoh session used by all bridges."""
        print(f"[MANAGER] Opening Zenoh session to {ZENOH_ENDPOINT}...")
        config = zenoh.Config()
        config.insert_json5("connect/endpoints", f'["{ZENOH_ENDPOINT}"]')
        z = zenoh.open(config)
        print("[MANAGER] Zenoh session opened")
        return z
    
    def shutdown(self) -> None:
        """
        Stop all bridges + sensors and release resources:
        - signal sensor stop
        - signal all bridge stops
        - wait for tasks to end
        - close zenoh session
        - shutdown executor
        """
        print("[MANAGER] Shutting down...")

        # Stop sensors
        self._sensor_stop.set()

        # Stop all bridges
        for bridge_id in list(self._bridges.keys()):
            self.close_bridge(bridge_id)

        # Close Zenoh
        try:
            self._zenoh.close()
        except Exception:
            pass

        # Executor
        self._executor.shutdown(wait=True)

        print("[MANAGER] Shutdown complete")
    
    def start_sensors(self, *, enable_imu: bool = True, enable_dwm: bool = True, dwm_port: str = DWM_DEFAULT_PORT) -> None:
        if self._sensors_started:
            return

        if enable_imu:
            self._executor.submit(imu_worker, self._sensor_stop, self.state)

        if enable_dwm:
            self._executor.submit(dwm_worker, self._sensor_stop, self.state, dwm_port)

        self._sensors_started = True
        print("[MANAGER] Sensors started")
    
    def create_bridge(self, outbound_topic: str, message_type: MessageType) -> str:
        """
        Create a publishing bridge by submitting a publisher task to the executor.

        Returns a bridge_id used later to close it.
        """
        bridge_id = uuid.uuid4().hex
        stop = Event()

        fut = self._executor.submit(
            self._bridge_publisher_loop,
            stop,
            outbound_topic,
            message_type,
        )

        self._bridges[bridge_id] = BridgeHandle(
            outbound_topic=outbound_topic,
            message_type=message_type,
            stop=stop,
            future=fut,
        )

        print(f"[MANAGER] Bridge created id={bridge_id} type={message_type.value} topic={outbound_topic}")
        return bridge_id

    def close_bridge(self, bridge_id: str) -> None:
        """
        Stop a single bridge:
        - signal its stop event
        - optionally wait a moment for it to end (non-blocking is fine too)
        - remove it from registry
        """
        handle = self._bridges.get(bridge_id)
        if not handle:
            print(f"[MANAGER] close_bridge: no such id={bridge_id}")
            return

        print(f"[MANAGER] Closing bridge id={bridge_id} ...")
        handle.stop.set()

        # Optional: wait briefly or just drop it (future will end on its own)
        # handle.future.result(timeout=2.0)  # uncomment if you want strict join

        del self._bridges[bridge_id]
        print(f"[MANAGER] Bridge closed id={bridge_id}")

    def _bridge_publisher_loop(self, stop: Event, outbound_topic: str, message_type: MessageType) -> None:
        """
        Worker for one bridge.

        It:
        - wakes up every BRIDGE_PUBLISH_PERIOD_SEC
        - reads SharedState snapshot
        - encodes the data for message_type
        - publishes to outbound_topic
        - exits when stop is set
        """
        print(f"[BRIDGE] Start type={message_type.value} topic={outbound_topic} period={BRIDGE_PUBLISH_PERIOD_SEC}s")

        while not stop.is_set():
            snap = self.state.snapshot()

            payload = self._encode_payload(message_type, snap)
            if payload is not None:
                try:
                    self._zenoh.put(outbound_topic, payload)
                except Exception as e:
                    print(f"[BRIDGE] publish error topic={outbound_topic}: {e}")

            time.sleep(PUBLISH_PERIOD_SEC)

        print(f"[BRIDGE] Stop type={message_type.value} topic={outbound_topic}")
    
    def _encode_payload(self, message_type: MessageType, snap: dict) -> Optional[bytes]:
        """
        Convert a SharedState snapshot into bytes suitable for Zenoh.

        Right now: JSON bytes (easy for debugging).
        Later: swap to protobuf without changing bridge logic.
        """
        if message_type == MessageType.IMU:
            quat = snap["imu_quat"]
            if quat is None:
                return None
            data = {
                "type": "imu",
                "ts": snap["imu_ts"],
                "quat": {"i": quat[0], "j": quat[1], "k": quat[2], "w": quat[3]},
            }
            return json.dumps(data).encode()

        if message_type == MessageType.DWM:
            pos = snap["dwm_pos"]
            if pos is None:
                return None

            data = {"type": "dwm", "ts": snap["dwm_ts"]}

            # try common fields, else include raw
            found = False
            for name in ("x_m", "y_m", "z_m", "x", "y", "z"):
                if hasattr(pos, name):
                    data[name] = float(getattr(pos, name))
                    found = True
            if not found:
                data["raw"] = str(pos)

            return json.dumps(data).encode()

        # Unknown message type
        return None

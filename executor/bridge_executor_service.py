# bridge_executor_service.py
import time
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Event, Lock
from typing import Dict, Optional
from dataclasses import dataclass
import json
import uuid

import zenoh
from google.protobuf.message import DecodeError

import bridge_request_pb2 as bridge_pb

from constants import (
    PUBLISH_PERIOD_SEC,
    DWM_DEFAULT_PORT,
)
from shared_state import SharedState
from message_types import MessageType
from imu_executor_test import imu_worker
from dwm_executor_test import dwm_worker
from service_utils import make_service_reply


def _proto_to_msg_type(mt: int) -> MessageType:
    if mt == bridge_pb.IMU:
        return MessageType.IMU
    if mt == bridge_pb.DWM:
        return MessageType.DWM
    raise ValueError(f"Unknown BridgeMessageType: {mt}")


@dataclass
class BridgeHandle:
    """
    Tracks one running bridge publisher task.
    """
    outbound_topic: str
    message_type: MessageType
    stop: Event
    future: Future


class BridgeManager:
    """
    Unified bridge manager + bridge management service.
    """

    def __init__(self, session: zenoh.Session, resource_name: str, *, max_workers: int = 6):
        self.state = SharedState(_lock=Lock())
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        self._zenoh = session
        self._resource_name = resource_name

        self._sensor_stop = Event()
        self._sensors_started = False

        self._bridges: Dict[str, BridgeHandle] = {}

        self._token = self._zenoh.liveliness().declare_token(resource_name)
        self._open_q = self._zenoh.declare_queryable(
            resource_name + "/open_bridge",
            self.handle_open_bridge,
        )
        self._close_q = self._zenoh.declare_queryable(
            resource_name + "/close_bridge",
            self.handle_close_bridge,
        )

    def start_sensors(self, *, enable_imu: bool = True, enable_dwm: bool = True, dwm_port: str = DWM_DEFAULT_PORT) -> None:
        """
        Submit sensor tasks to the executor. Sensors write to SharedState.
        """
        if self._sensors_started:
            return

        if enable_imu:
            self._executor.submit(imu_worker, self._sensor_stop, self.state)

        if enable_dwm:
            self._executor.submit(dwm_worker, self._sensor_stop, self.state, dwm_port)

        self._sensors_started = True
        print("[BRIDGE_MGR] Sensors started")

    def open_bridge(self, outbound_topic: str, message_type: MessageType) -> str:
        """
        Create a publishing bridge task and return bridge_id.
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

        print(f"[BRIDGE_MGR] Bridge opened id={bridge_id} type={message_type.value} topic={outbound_topic}")
        return bridge_id

    def close_bridge(self, bridge_id: str) -> None:
        """
        Stop a single bridge by signaling its stop Event.
        Raises ValueError if bridge_id does not exist.
        """
        handle = self._bridges.get(bridge_id)
        if not handle:
            raise ValueError(f"No bridge with id '{bridge_id}'")

        print(f"[BRIDGE_MGR] Closing bridge id={bridge_id} ...")
        handle.stop.set()
        del self._bridges[bridge_id]
        print(f"[BRIDGE_MGR] Bridge closed id={bridge_id}")

    def handle_open_bridge(self, query: zenoh.Query) -> None:
        """
        Zenoh query handler for open_bridge.

        Expects:
            bridge_pb.OpenBridgeRequest

        Replies with:
            ServiceReply
        """
        try:
            req = bridge_pb.OpenBridgeRequest()
            req.ParseFromString(query.payload.to_bytes())

            self.open_bridge(
                req.outbound_topic,
                _proto_to_msg_type(req.message_type),
            )

            rep = make_service_reply(
                is_successful=True,
                message="Bridge created successfully",
                error="",
            )

            query.reply(
                self._open_q.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString()),
            )

        except DecodeError:
            rep = make_service_reply(
                is_successful=False,
                message="Unable to parse open_bridge request",
                error="DecodeError",
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Exception as e:
            rep = make_service_reply(
                is_successful=False,
                message="Failed to open bridge",
                error=str(e),
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

    def handle_close_bridge(self, query: zenoh.Query) -> None:
        """
        Zenoh query handler for close_bridge.

        Expects:
            bridge_pb.CloseBridgeRequest

        Replies with:
            ServiceReply
        """
        try:
            req = bridge_pb.CloseBridgeRequest()
            req.ParseFromString(query.payload.to_bytes())

            self.close_bridge(req.bridge_id)

            rep = make_service_reply(
                is_successful=True,
                message=f"Bridge '{req.bridge_id}' closed successfully",
                error="",
            )

            query.reply(
                self._close_q.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString()),
            )

        except DecodeError:
            rep = make_service_reply(
                is_successful=False,
                message="Unable to parse close_bridge request",
                error="DecodeError",
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Exception as e:
            rep = make_service_reply(
                is_successful=False,
                message="Failed to close bridge",
                error=str(e),
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

    def _bridge_publisher_loop(self, stop: Event, outbound_topic: str, message_type: MessageType) -> None:
        """
        Worker for one bridge: periodically publish from SharedState to Zenoh.
        """
        print(f"[BRIDGE] Start type={message_type.value} topic={outbound_topic} period={PUBLISH_PERIOD_SEC}s")

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
        Encode SharedState snapshot -> bytes. Currently JSON.
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
            found = False
            for name in ("x_m", "y_m", "z_m", "x", "y", "z"):
                if hasattr(pos, name):
                    data[name] = float(getattr(pos, name))
                    found = True
            if not found:
                data["raw"] = str(pos)

            return json.dumps(data).encode()

        return None

    def stop(self) -> None:
        """
        Undeclare the bridge management queryables.
        """
        self._open_q.undeclare()
        self._close_q.undeclare()

    def shutdown(self) -> None:
        """
        Stop all bridges + sensors, queryables, and shut down executor.
        """
        print("[BRIDGE_MGR] Shutting down...")

        self.stop()
        self._sensor_stop.set()

        for bridge_id in list(self._bridges.keys()):
            try:
                self.close_bridge(bridge_id)
            except Exception as e:
                print(f"[BRIDGE_MGR] Error closing bridge {bridge_id}: {e}")

        self._executor.shutdown(wait=True)
        print("[BRIDGE_MGR] Shutdown complete")
    


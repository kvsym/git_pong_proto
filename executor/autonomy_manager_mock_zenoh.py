from google.protobuf.wrappers_pb2 import BoolValue, StringValue
from google.protobuf.message import DecodeError

import rtr.pb2 as rtr
import bridge_request.pb2 as bridge_pb

import zenoh

import yaml

import sys
from pathlib import Path
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
import time
import threading
from threading import Event
from queue import Queue, Full, Empty
from functools import partial

import utils as aou

logging.basicConfig(level=logging.INFO)

from message_types import MessageType
from service_utils import make_service_reply

def _proto_to_msg_type(mt: int) -> MessageType:
    if mt == bridge_pb.IMU:
        return MessageType.IMU
    if mt == bridge_pb.DWM:
        return MessageType.DWM
    raise ValueError(f"Unknown BridgeMessageType: {mt}")

class BridgeMgmtService:
    def __init__(self, session: zenoh.Session, bridge_mgr, resource_name: str):
        self._session = session
        self._bridge_mgr = bridge_mgr
        self._resource_name = resource_name
        self._token = self._session.liveliness().declare_token(resource_name)

        self._open_q = self._session.declare_queryable(
            resource_name + "/open_bridge",
            self.handle_open_bridge
        )
        self._close_q = self._session.declare_queryable(
            resource_name + "/close_bridge",
            self.handle_close_bridge
        )

    def handle_open_bridge(self, query: zenoh.Query):
        try:
            req = bridge_pb.OpenBridgeRequest()
            req.ParseFromString(query.payload.to_bytes())

            bridge_id = self._bridge_mgr.open_bridge(
                req.outbound_topic,
                _proto_to_msg_type(req.message_type)
            )

            rep = bridge_pb.OpenBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=True,
                message="Bridge created successfully",
                error=""
            ))

            query.reply(
                self._open_q.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString())
            )

        except DecodeError:
            rep = bridge_pb.OpenBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=False,
                message="Unable to parse open_bridge request",
                error="DecodeError"
            ))

            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Exception as e:
            rep = bridge_pb.OpenBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=False,
                message="Failed to open bridge",
                error=str(e)
            ))

            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

    def handle_close_bridge(self, query: zenoh.Query):
        try:
            req = bridge_pb.CloseBridgeRequest()
            req.ParseFromString(query.payload.to_bytes())

            self._bridge_mgr.close_bridge(req.bridge_id)

            rep = bridge_pb.CloseBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=True,
                message=f"Bridge '{req.bridge_id}' closed successfully",
                error=""
            ))

            query.reply(
                self._close_q.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString())
            )

        except DecodeError:
            rep = bridge_pb.CloseBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=False,
                message="Unable to parse close_bridge request",
                error="DecodeError"
            ))
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Exception as e:
            rep = bridge_pb.CloseBridgeReply()
            rep.status.CopyFrom(make_service_reply(
                is_successful=False,
                message="Failed to close bridge",
                error=str(e)
            ))
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

    def stop(self):
        self._open_q.undeclare()
        self._close_q.undeclare()

'''
Alternative implementation using Zenoh query/reply framework.
'''
class TaskManagementService:

    def __init__(self, session : zenoh.Session, task_queue : Queue, resource_name : str):
        self._session = session
        self._task_queue = task_queue
        self._resource_name = resource_name
        self._token = self._session.liveliness().declare_token(resource_name)

        self._submit_task_queryable = self._session.declare_queryable(
            resource_name + "/submit_task",
            self.handle_submit_task
        )
        self._cancel_task_queryable = self._session.declare_queryable(
            resource_name + "/cancel_task",
            self.handle_cancel_task
        )

    def handle_submit_task(self, query : zenoh.Query):
        try:
            taskatt_msg = rtr.TaskAttempt()
            taskatt_msg.ParseFromString(query.payload.to_bytes())
            logging.getLogger(__name__).info(f"Received new TaskAttempt:\n{taskatt_msg}")

            self._task_queue.put_nowait(taskatt_msg)

            rep = make_service_reply(
                is_successful=True,
                message="Task submitted successfully",
                error=""
            )
            query.reply(
                self._submit_task_queryable.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString())
            )

        except DecodeError:
            rep = make_service_reply(
                is_successful=False,
                message="Unable to parse TaskAttempt payload",
                error="DecodeError"
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Full:
            rep = make_service_reply(
                is_successful=False,
                message="Task queue is full",
                error="QueueFull"
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

    def handle_cancel_task(self, query: zenoh.Query):
        try:
            task_name = StringValue()
            task_name.ParseFromString(query.payload.to_bytes())
            logging.getLogger(__name__).info(f"Received cancel request for {task_name}")

            self._task_queue.put_nowait("cancel")

            rep = make_service_reply(
                is_successful=True,
                message=f"Cancel request accepted for task '{task_name.value}'",
                error=""
            )
            query.reply(
                self._cancel_task_queryable.key_expr,
                payload=zenoh.ZBytes(rep.SerializeToString())
            )

        except DecodeError:
            rep = make_service_reply(
                is_successful=False,
                message="Unable to parse cancel request payload",
                error="DecodeError"
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))

        except Full:
            rep = make_service_reply(
                is_successful=False,
                message="Task queue is full; unable to enqueue cancel request",
                error="QueueFull"
            )
            query.reply_err(payload=zenoh.ZBytes(rep.SerializeToString()))


    def stop(self):
        self._submit_task_queryable.undeclare()
        self._cancel_task_queryable.undeclare()


class AutonomyManager:
    """
    backend/bridge_mgmt/open_bridge

    backend/bridge_mgmt/close_bridge
    """
    def __init__(self, config):
        from bridge_executor_service import BridgeManager

        # Create BridgeManager USING THE SAME SESSION
        self._bridge_mgr = BridgeManager(self._zenoh_sesh, max_workers=6)

        # Start sensor tasks (configurable)
        self._bridge_mgr.start_sensors(enable_imu=True, enable_dwm=True)

        # Create Bridge Management Service (queryables)
        self._bridge_mgmt = BridgeMgmtService(
            self._zenoh_sesh,
            self._bridge_mgr,
            aou.QueryableServices.BRIDGE_MGMT
        )

        self._task_queue = Queue(maxsize=1)
        logging.getLogger(__name__).info("Initializing AutonomyManager...")

        self._zenoh_sesh = zenoh.open(zenoh.Config().from_file(Path(__file__).parent / "config" / "acl_config.json"))

        self._curr_task_name = ""
        self._task_machine = None
        self._exec_period = float(config.get("exec_period", 0.2))
        queriers_cfg = config.get("queriers", None)

        # Create queriers for any required services.
        self._queriers_dict : Dict[str, zenoh.Querier] = {}
        if queriers_cfg:
            for service, ops in queriers_cfg.items():
                for op in ops:
                    key = f"{aou.QueryableServices.BACKEND}/{service}/{op}"
                    self._queriers_dict[f"{aou.QueryableServices.BACKEND}/{service}/{op}"] = self._zenoh_sesh.declare_querier(
                        f"{aou.QueryableServices.BACKEND}/{service}/{op}"
                    )
        logging.getLogger(__name__).info(f"Service queriers created:\n{list(self._queriers_dict.keys())}")

        logging.getLogger(__name__).info("Creating Task Management Service")
        self._task_mgmt = TaskManagementService(self._zenoh_sesh, self._task_queue, aou.QueryableServices.TASK_MGMT)

        logging.getLogger(__name__).info("Done.")

    def run(self):
        while True:
            time.sleep(self._exec_period)
            # Do stuff
            try:
                new_task = self._task_queue.get_nowait()
                if new_task == "cancel":
                    logging.getLogger(__name__).info(f"Canceling current task: {self._curr_task_name}")
                    self._task_machine = None
                else:
                    self._curr_task_name = new_task.task.task_name
                    self._task_machine = "*placeholder TM*"
                    logging.getLogger(__name__).info(f"Received new task:\n{new_task}")
            except Empty:
                pass

            if self._task_machine:
                logging.getLogger(__name__).info(f"Executing new task: {self._curr_task_name}")

    def shutdown(self):
        logging.getLogger(__name__).warning("Autonomy Manager shutting down.")
        self._task_mgmt.stop()
        self._bridge_mgmt.stop()
        self._bridge_mgr.shutdown()      # stops tasks/executor only
        self._zenoh_sesh.close()         # closes the ONE shared session

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", 
        default="autonomy_mgr_cfg.yaml",
        help="The path to the yaml-based config file.")
    
    args = parser.parse_args()
    config_path = Path(__file__).parent / "config" / args.config
    logging.getLogger().info(f"Config path = {config_path}")

    try:
        config_file = open(config_path, "r")
        config = yaml.safe_load(config_file)
        config_file.close()
    except FileNotFoundError:
        logging.getLogger(__name__).error(f"{config_path} not found!")
        sys.exit()

    try:
        am = AutonomyManager(config)
        am.run()

    except KeyboardInterrupt:
        am.shutdown()

if __name__ == '__main__':
    main()
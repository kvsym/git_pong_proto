# main.py
import time
import argparse

from executor.bridge_executor_service import BridgeManager
from message_types import MessageType


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-imu", action="store_true")
    parser.add_argument("--no-dwm", action="store_true")

    # Create bridge specs from CLI (repeatable)
    # Example:
    #   --bridge human/imu imu --bridge human/dwm dwm
    parser.add_argument(
        "--bridge",
        action="append",
        nargs=2,
        metavar=("TOPIC", "TYPE"),
        help="Bridge spec: TOPIC TYPE  (TYPE in {imu,dwm})",
    )
    args = parser.parse_args()

    mgr = BridgeManager(max_workers=6)
    mgr.start_sensors(enable_imu=not args.no_imu, enable_dwm=not args.no_dwm)

    # Create requested bridges
    bridge_ids = []
    if args.bridge:
        for topic, typ in args.bridge:
            msg_type = MessageType(typ)  # validates enum
            bridge_ids.append(mgr.create_bridge(topic, msg_type))
    else:
        # default bridges if none specified
        bridge_ids.append(mgr.create_bridge("human/imu", MessageType.IMU))
        bridge_ids.append(mgr.create_bridge("human/dwm", MessageType.DWM))

    try:
        # keep running
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        # Close bridges (optional; shutdown() already closes them)
        for bid in bridge_ids:
            mgr.close_bridge(bid)
        mgr.shutdown()


if __name__ == "__main__":
    main()
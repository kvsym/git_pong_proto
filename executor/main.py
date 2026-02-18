import argparse
from executor.bridge_executor_service import Bridge
from executor.constants import DWM_DEFAULT_PORT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dwm-port", default=DWM_DEFAULT_PORT)
    parser.add_argument("--no-dwm", action="store_true")
    parser.add_argument("--no-imu", action="store_true")
    args = parser.parse_args()

    bridge = Bridge(
        dwm_port=args.dwm_port,
        enable_dwm=not args.no_dwm,
        enable_imu=not args.no_imu,
    )

    bridge.create_bridge()

    try:
        # main thread just blocks until Ctrl+C
        while True:
            pass
    except KeyboardInterrupt:
        bridge.close_bridge()

if __name__ == "__main__":
    main()
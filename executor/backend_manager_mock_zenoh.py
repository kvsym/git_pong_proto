from pathlib import Path
import argparse
import logging
import time
from typing import Optional

import zenoh

import utils as aou
from bridge_executor_service import BridgeManager

logging.basicConfig(level=logging.INFO)


class BackendManager:
    """
    Bridge-only backend manager.

    Responsibilities:
    - Own the shared Zenoh session
    - Create and own the BridgeManager
    - Start sensor workers
    - Keep the process alive when run as an application
    - Shut everything down cleanly
    """

    def __init__(
        self,
        exec_period: float = 0.2,
        enable_imu: bool = True,
        enable_dwm: bool = True,
        dwm_port: str = "/dev/ttyACM0",
        zenoh_endpoint: Optional[str] = None,
    ):
        """
        Store configuration only. Do not start network/session/sensors here.

        Args:
            exec_period: Sleep period for the top-level run loop.
            enable_imu: Whether to start the IMU sensor worker.
            enable_dwm: Whether to start the DWM sensor worker.
            dwm_port: Serial port for the DWM device.
            zenoh_endpoint: Optional Zenoh router endpoint, e.g. tcp/192.168.1.50:7447.
                            If None, Zenoh default discovery/config is used.
        """
        self._exec_period = float(exec_period)
        self._enable_imu = bool(enable_imu)
        self._enable_dwm = bool(enable_dwm)
        self._dwm_port = str(dwm_port)
        self._zenoh_endpoint = zenoh_endpoint

        self._zenoh_sesh: Optional[zenoh.Session] = None
        self._bridge_mgr: Optional[BridgeManager] = None
        self._is_started = False
        self._is_shutdown = False

    def start(self) -> None:
        """
        Start the backend manager.

        This:
        - opens the shared Zenoh session
        - creates the BridgeManager
        - starts the configured sensor workers

        Safe to call once. Calling it multiple times is a no-op.
        """
        if self._is_started:
            logging.getLogger(__name__).info("BackendManager already started.")
            return

        logging.getLogger(__name__).info("Initializing BackendManager...")

        # Open shared Zenoh session WITHOUT a config file
        config = zenoh.Config()
        if self._zenoh_endpoint:
            config.insert_json5("connect/endpoints", f'["{self._zenoh_endpoint}"]')

        self._zenoh_sesh = zenoh.open(config)

        # Create BridgeManager using the SAME session
        self._bridge_mgr = BridgeManager(
            self._zenoh_sesh,
            aou.QueryableServices.BRIDGE_MGMT,
            max_workers=6,
        )

        # Start sensors
        self._bridge_mgr.start_sensors(
            enable_imu=self._enable_imu,
            enable_dwm=self._enable_dwm,
            dwm_port=self._dwm_port,
        )

        self._is_started = True
        logging.getLogger(__name__).info("BackendManager started successfully.")

    def run_forever(self) -> None:
        """
        Keep the process alive.

        All real work happens in:
        - BridgeManager executor tasks
        - Zenoh callbacks/query handlers
        """
        if not self._is_started:
            self.start()

        try:
            while True:
                time.sleep(self._exec_period)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self) -> None:
        """
        Cleanly shut down the backend manager.
        """
        if self._is_shutdown:
            return

        logging.getLogger(__name__).warning("BackendManager shutting down.")

        if self._bridge_mgr is not None:
            self._bridge_mgr.shutdown()
            self._bridge_mgr = None

        if self._zenoh_sesh is not None:
            self._zenoh_sesh.close()
            self._zenoh_sesh = None

        self._is_shutdown = True
        self._is_started = False

    @property
    def bridge_manager(self) -> Optional[BridgeManager]:
        return self._bridge_mgr

    @property
    def zenoh_session(self) -> Optional[zenoh.Session]:
        return self._zenoh_sesh


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    parser.add_argument("--exec-period", type=float, default=0.2)
    parser.add_argument("--no-imu", action="store_true")
    parser.add_argument("--no-dwm", action="store_true")
    parser.add_argument("--dwm-port", default="/dev/ttyACM0")
    parser.add_argument(
        "--zenoh-endpoint",
        default=None,
        help='Optional Zenoh router endpoint, e.g. "tcp/192.168.1.50:7447"',
    )

    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    backend = BackendManager(
        exec_period=args.exec_period,
        enable_imu=not args.no_imu,
        enable_dwm=not args.no_dwm,
        dwm_port=args.dwm_port,
        zenoh_endpoint=args.zenoh_endpoint,
    )

    backend.start()
    backend.run_forever()


if __name__ == "__main__":
    main()
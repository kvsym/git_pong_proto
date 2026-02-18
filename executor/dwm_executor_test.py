import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from executor.constants import (
    DWM_DEFAULT_PORT, DWM_BAUD, DWM_SERIAL_TIMEOUT_SEC,
    DWM_POLL_SEC, BRIDGE_PRINT_SEC
)
from executor.shared_state import SharedState


def dwm_worker(stop: Event, state: SharedState, port: str) -> None:
    from serial import Serial

    import dwm1001
    """
    Background worker for DWM1001 (or similar serial sensor).

    - Opens serial port
    - Starts position reporting
    - Continuously reads position
    - Writes latest position to SharedState
    """
    print(f"[DWM] Initializing on {port}...")
    ser = Serial(port, baudrate=DWM_BAUD, timeout=DWM_SERIAL_TIMEOUT_SEC)
    tag = dwm1001.ActiveTag(ser)
    tag.start_position_reporting()
    print("[DWM] Worker started")

    while not stop.is_set():
        try:
            pos = tag.position
            if pos:
                state.set_dwm_pos(pos)
        except Exception:
            pass
        time.sleep(DWM_POLL_SEC)

    print("[DWM] Worker stopping")


def main() -> None:
    stop = Event()
    state = SharedState(_lock=Lock())

    with ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(dwm_worker, stop, state, DWM_DEFAULT_PORT)

        try:
            while True:
                snap = state.snapshot()
                print("[MAIN] Latest position:", snap["dwm_pos"])
                time.sleep(BRIDGE_PRINT_SEC)
        except KeyboardInterrupt:
            print("\n[MAIN] Stopping...")
            stop.set()


if __name__ == "__main__":
    main()
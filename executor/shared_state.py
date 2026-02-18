from dataclasses import dataclass
from threading import Lock
from typing import Optional, Tuple, Any
import time

# Quaternion type alias (IMU orientation)
Quat = Tuple[float, float, float, float]


@dataclass
class SharedState:
    """
    Thread-safe shared memory object.

    All sensor threads write here.
    All consumers (tasks, Zenoh, logging) read from here.
    """
    _lock: Lock
    imu_quat: Optional[Quat] = None
    imu_ts: float = 0.0

    dwm_pos: Optional[Any] = None
    dwm_ts: float = 0.0

    def set_imu_quat(self, quat: Quat) -> None:
        """
        Update the latest IMU quaternion.

        Uses a lock to prevent race conditions when multiple
        threads read/write simultaneously.
        """
        with self._lock:
            self.imu_quat = quat
            self.imu_ts = time.time()

    def set_dwm_pos(self, pos: Any) -> None:
        """
        Update the latest DWM position.
        """
        with self._lock:
            self.dwm_pos = pos
            self.dwm_ts = time.time()

    def snapshot(self) -> dict:
        """
        Take an atomic snapshot of all shared state.

        This ensures consumers see a consistent view.
        """
        with self._lock:
            return {
                "imu_quat": self.imu_quat,
                "imu_ts": self.imu_ts,
                "dwm_pos": self.dwm_pos,
                "dwm_ts": self.dwm_ts,
            }

# ---- Timing ----
IMU_POLL_SEC = 0.05
DWM_POLL_SEC = 0.10
BRIDGE_PRINT_SEC = 1.0
TASK_PERIOD_SEC = 0.50
WAIT_FIRST_DATA_SEC = 0.10

# ---- DWM / Serial ----
DWM_DEFAULT_PORT = "/dev/ttyACM0"
DWM_BAUD = 115_200
DWM_SERIAL_TIMEOUT_SEC = 1.0

# ---- Zenoh ----
ZENOH_ENDPOINT = "tcp/localhost:7447"

# ---- IMU thresholds (example for task logic) ----
STABLE_W_THRESHOLD = 0.50

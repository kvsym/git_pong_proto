# ---- Timing ----
IMU_POLL_SEC = 0.05
DWM_POLL_SEC = 0.10

PUBLISH_PERIOD_SEC = 0.10  # per bridge publisher loop rate

# ---- DWM / Serial ----
DWM_DEFAULT_PORT = "/dev/ttyACM0"
DWM_BAUD = 115_200
DWM_SERIAL_TIMEOUT_SEC = 1.0

# ---- Zenoh ----
ZENOH_ENDPOINT = "tcp/localhost:7447"

# ---- IMU thresholds (example for task logic) ----
STABLE_W_THRESHOLD = 0.50


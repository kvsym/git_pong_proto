# ---- Worker timing ----
IMU_POLL_SEC = 0.05
DWM_POLL_SEC = 0.10
PUBLISH_PERIOD_SEC = 0.10   # publish loop rate 

# ---- Serial / DWM ----
DWM_DEFAULT_PORT = "/dev/ttyACM0"
DWM_BAUD = 115_200
DWM_TIMEOUT_SEC = 1.0

# ---- Zenoh ----
ZENOH_ENDPOINT = "tcp/localhost:7447"
ZENOH_KEY_IMU = "human/imu"
ZENOH_KEY_DWM = "human/dwm"

# ---- IMU thresholds (example for task logic) ----
STABLE_W_THRESHOLD = 0.50

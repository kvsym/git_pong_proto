import asyncio
import argparse
import zenoh
import board
import busio
from adafruit_bno08x import (
    BNO_REPORT_ROTATION_VECTOR,
    BNO_REPORT_ACCELEROMETER,
)
from adafruit_bno08x.i2c import BNO08X_I2C


# ---------------- PING ---------------- #

def run_ping(z):
    """Ping node: sends ping and receives IMU orientation."""
    def pong_callback(sample):
        payload = bytes(sample.payload).decode(errors="ignore")
        print(f"[PING] Orientation received: {payload}")

    z.declare_subscriber("pong", pong_callback)

    counter = 0
    print("[PING] Running...")
    try:
        while True:
            z.put("ping", b"ping")
            counter += 1
            print(f"[PING] Sent ping #{counter}")
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PING] Stopped")


# ---------------- PONG ---------------- #

def run_pong(z):
    """Pong node: reads BNO085 orientation and responds to ping."""
    first_ping_received = False
    latest_orientation = "unknown"

    # Init I2C + IMU
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        print("[PONG] BNO085 initialized")
    except Exception as e:
        print(f"[ERROR] IMU init failed: {e}")
        return

    def ping_callback(sample):
        nonlocal first_ping_received, latest_orientation
        first_ping_received = True
        print("[PONG] Ping received")

        try:
            quat = bno.quaternion  # (i, j, k, real)
            if quat:
                i, j, k, r = quat
                latest_orientation = (
                    f"quat=[{i:.3f}, {j:.3f}, {k:.3f}, {r:.3f}]"
                )
        except Exception:
            pass

    z.declare_subscriber("ping", ping_callback)

    print("[PONG] Waiting for first ping...")
    while not first_ping_received:
        asyncio.run(asyncio.sleep(0.1))

    counter = 0
    try:
        while True:
            counter += 1
            msg = f"pong#{counter}: {latest_orientation}"
            z.put("pong", msg.encode())
            print(f"[PONG] Sent: {msg}")
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PONG] Stopped")


# ---------------- MAIN ---------------- #

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["ping", "pong"], required=True)
    args = parser.parse_args()

    print("[INFO] Connecting to Zenoh router...")
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", '["tcp/localhost:7447"]')
    z = zenoh.open(config)
    print("[INFO] Zenoh connected")

    if args.role == "ping":
        run_ping(z)
    else:
        run_pong(z)


if __name__ == "__main__":
    main()
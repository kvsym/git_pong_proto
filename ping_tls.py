import asyncio
import argparse
from pathlib import Path
import sys
import zenoh

# Adafruit TSL2591 imports
import board
import busio
import adafruit_tsl2591


def run_ping(z):
    """Ping node: sends 'ping' and listens for sensor replies from pong."""
    def pong_callback(sample):
        payload = bytes(sample.payload).decode(errors="ignore")
        print(f"[PING] Received sensor data: {payload}")

    z.declare_subscriber("pong", pong_callback)

    counter = 0
    print("[PING] Starting ping loop...")
    try:
        while True:
            z.put("ping", b"ping")
            counter += 1
            print(f"[PING] Sent ping #{counter}")
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PING] Stopped")


def run_pong(z):
    """Pong node: reads light data from TSL2591 and responds to pings."""
    counter = 0
    first_ping_received = False
    latest_light = "unknown"

    # Initialize I2C + TSL2591
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_tsl2591.TSL2591(i2c)
        print("[PONG] TSL2591 light sensor initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize TSL2591: {e}")
        return

    def ping_callback(sample):
        nonlocal first_ping_received, latest_light
        first_ping_received = True
        print("[PONG] Got ping")

        try:
            lux = sensor.lux
            visible = sensor.visible
            infrared = sensor.infrared

            latest_light = (
                f"lux={lux:.2f}, visible={visible}, infrared={infrared}"
            )
        except Exception as e:
            latest_light = "sensor read error"

    z.declare_subscriber("ping", ping_callback)

    print("[PONG] Waiting for first ping...")
    while not first_ping_received:
        asyncio.run(asyncio.sleep(0.1))

    try:
        while True:
            counter += 1
            msg = f"pong#{counter}: {latest_light}"
            z.put("pong", msg.encode())
            print(f"[PONG] Sent sensor update: {msg}")
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PONG] Stopped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["ping", "pong"], required=True)
    args = parser.parse_args()

    print("[INFO] Connecting to Zenoh router at tcp/localhost:7447...")
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", '["tcp/localhost:7447"]')
    z = zenoh.open(config)
    print("[INFO] Zenoh session opened")

    if args.role == "ping":
        run_ping(z)
    else:
        run_pong(z)


if __name__ == "__main__":
    main()

import asyncio
import argparse
from pathlib import Path
import sys
from serial import Serial
import zenoh
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))
import dwm1001

import position_pb2

def run_ping(z):
    def pong_callback(sample):
        try:
            msg = position_pb2.Position()
            msg.ParseFromString(bytes(sample.payload))
            print(f"[PING] Received position: seq={msg.seq} source={msg.source} "f"x={msg.x_m:.3f} y={msg.y_m: .3f} z={msg.z_m:.3f}")
        except Exception as e:
            try:
                print(f"[PING] Received (non-proto): {bytes(sample.payload).decode(errors='ignore')}")
            except Exception:
                print(f"[PING] Received (non-proto binary, len={len(sample.payload)} bytes)")
            print(f"[PING] decode error: {e}")
    z.declare_subscriber("pong", pong_callback)
    counter = 0
    print("[PING] starting ping loop...")
    try:
        while True:
            z.put("ping", b"ping")
            counter += 1
            print(f"[PING] Sent ping number {counter}")
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PING] Stopped")

def run_pong(z, serial_port="/dev/ttyACM0"):
    counter = 0
    first_ping_received = False
    latest_position = position_pb2.Position()
    latest_position.seq = 0
    latest_position.source = "unknown"
    try:
        serial_handle = Serial(serial_port, baudrate=115200, timeout=1)
        tag = dwm1001.ActiveTag(serial_handle)
        tag.start_position_reporting()
        print(f"[PONG] Connected to Qorvo tag at {serial_port}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Qorvo tag: {e}")
        return

    def ping_callback(sample):
        nonlocal first_ping_received, latest_position
        first_ping_received = True
        payload = bytes(sample.payload).decode(errors="ignore")
        print(f"[PONG] Got ping: {payload}")

        try:
            pos = tag.position
            if pos:
                latest_position = position_pb2.Position()
                latest_position.x_m = pos.x_m
                latest_position.y_m = pos.y_m
                latest_position.z_m = pos.z_m
                latest_position.seq += 1
                latest_position.source = "qorvo-tag"
        except Exception as e:
            pass
    z.declare_subscriber("ping", ping_callback)
    print("[PONG] Waiting for first ping...")
    while not first_ping_received:
        asyncio.run(asyncio.sleep(0.1))
    try:
        while True:
            counter += 1
            try:
                payload = latest_position.SerializeToString()
                z.put("pong", payload)
                print(f"[PONG] Sent position update: seq={latest_position.seq} " f"x={latest_position.x_m:.3f} y={latest_position.y_m:.3f} z={latest_position.z_m:.3f}")
            except Exception as e:
                print(f"[PONG] Failed to serialize/send protobuf: {e}")
                raw_msg = f"pong number {counter}: x={latest_position.x_m},y={latest_position.y_m},z={latest_position.z_m}"
                z.put("pong", raw_msg.encode())
            asyncio.run(asyncio.sleep(1.0))
    except KeyboardInterrupt:
        print("[PONG] Stopped")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["ping", "pong"], required=True)
    parser.add_argument("--serial", default="/dev/ttyACM0")
    args = parser.parse_args()
    print("[INFO] Connecting to Zenoh router")
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", f'["tcp/localhost:7447"]')
    z = zenoh.open(config)
    print("[INFO] Zenoh session opened")

    if args.role == "ping":
        run_ping(z)
    else:
        run_pong(z, args.serial)

if __name__ == "__main__":
    main()

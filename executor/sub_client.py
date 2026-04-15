import argparse
import time

import zenoh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zenoh-endpoint",
        default=None,
        help='Optional Zenoh router endpoint, e.g. "tcp/192.168.1.50:7447"',
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Topic to subscribe to, e.g. human/imu",
    )
    args = parser.parse_args()

    config = zenoh.Config()
    if args.zenoh_endpoint:
        config.insert_json5("connect/endpoints", f'["{args.zenoh_endpoint}"]')

    z = zenoh.open(config)

    def listener(sample):
        try:
            payload = sample.payload.to_bytes().decode()
        except Exception:
            payload = str(sample.payload.to_bytes())

        print(f"[{sample.key_expr}] {payload}")

    sub = z.declare_subscriber(args.topic, listener)

    print(f"Subscribed to {args.topic}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        sub.undeclare()
        z.close()


if __name__ == "__main__":
    main()
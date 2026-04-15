import argparse
import zenoh
import bridge_request_pb2 as bridge_pb
import service_reply_pb2 as service_reply_pb

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zenoh-endpoint", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--type", required=True, choices=["imu", "dwm"])
    args = parser.parse_args()

    config = zenoh.Config()
    config.insert_json5("connect/endpoints", f'["{args.zenoh_endpoint}"]')
    z = zenoh.open(config)

    req = bridge_pb.OpenBridgeRequest()
    req.outbound_topic = args.topic
    req.message_type = bridge_pb.IMU if args.type == "imu" else bridge_pb.DWM

    replies = z.get(
        "backend/bridge_mgmt/open_bridge",
        payload=req.SerializeToString(),
    )

    for reply in replies:
        if reply.ok is not None:
            rep = service_reply_pb.ServiceReply()
            rep.ParseFromString(reply.ok.payload.to_bytes())
            print("success:", rep.is_successful)
            print("message:", rep.message)
            print("error:", rep.error)
        else:
            print("Received error reply")

    z.close()

if __name__ == "__main__":
    main()
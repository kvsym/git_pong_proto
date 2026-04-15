import time
import service_reply_pb2 as service


def make_service_reply(
    *,
    is_successful: bool,
    message: str = "",
    error: str = "",
):
    reply = service.ServiceReply()
    reply.timestamp = int(time.time() * 1000)
    reply.is_successful = is_successful
    reply.message = message
    reply.error = error
    return reply
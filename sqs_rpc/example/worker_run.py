from typing import Any, Dict

from ..worker import RPCWorker

worker = RPCWorker(aws_region_name="us-east-1", polling_timeout_seconds=20)


@worker.queue("user-queue")
def handle_user_message(message) -> Dict[str, Any]:
    print(f"Processing user {message.user_id} action: {message.action}")
    return {"status": "success", "user_id": message.user_id}


@worker.queue("notification-queue")
def handle_notification(message) -> Dict[str, Any]:
    print(f"Sending notification to {message.recipient}: {message.content}")
    return {"status": "sent", "recipient": message.recipient}

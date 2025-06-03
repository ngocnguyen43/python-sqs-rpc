from .. import RPCClient


# Example message types
class UserMessage:
    def __init__(self, user_id: str, action: str):
        self.user_id = user_id
        self.action = action


class NotificationMessage:
    def __init__(self, recipient: str, content: str):
        self.recipient = recipient
        self.content = content


# Worker examp


# Client example
def create_client():
    return RPCClient(
        aws_region_name="us-east-1",
        polling_timeout_seconds=20,
        max_wait_time_seconds=30,
    )


def main():
    # Create a client
    client = create_client()

    # Example: Send a user message and wait for response
    user_response = client.publish(
        queue_name="user-queue",
        payload=UserMessage(user_id="123", action="login"),
        response_queue_name="response-queue",
    )
    print(f"User message response: {user_response}")

    # Example: Send a notification without waiting for response
    client.publish(
        queue_name="notification-queue",
        payload=NotificationMessage(recipient="user@example.com", content="Hello!"),
        wait_for_response=False,
    )


if __name__ == "__main__":
    main()

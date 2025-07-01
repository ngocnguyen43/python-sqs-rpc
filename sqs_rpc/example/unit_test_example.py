from sqs_rpc.testing import TestRPCManager

if __name__ == "__main__":
    # Example usage outside of Django
    with TestRPCManager() as rpc_manager:
        mock_client = rpc_manager.get_client()
        mock_worker = rpc_manager.get_worker()

        # Set up worker
        @mock_worker.queue("example-queue")
        def example_handler(data):
            return {"message": f"Hello, {data['name']}!"}

        # Test RPC call
        result = mock_client.publish(
            queue_name="example-queue",
            payload={"name": "World"},
            response_queue_name="example-response-queue",
            wait_for_response=True,
        )

        print(f"Result: {result}")

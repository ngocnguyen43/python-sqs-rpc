"""
Django Test Example for SQS RPC

This example shows how to use the testing utilities to mock RPC functionality
during Django tests without requiring actual AWS SQS connections.
"""

import json

from django.http import JsonResponse
from django.test import TestCase
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# Import the testing utilities
from sqs_rpc.testing import (
    TestRPCManager,
    get_test_rpc_manager,
    mock_rpc_for_testing,
)


# Example Django view that uses RPC
@method_decorator(csrf_exempt, name="dispatch")
class UserServiceView(View):
    """Example Django view that uses RPC to communicate with a user service."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # In production, this would be a real RPCClient
        self.rpc_client = None

    def set_rpc_client(self, client):
        """Set the RPC client (used for testing)."""
        self.rpc_client = client

    def post(self, request):
        """Create a user via RPC."""
        try:
            data = json.loads(request.body)
            user_data = {
                "name": data.get("name"),
                "email": data.get("email"),
                "age": data.get("age"),
            }

            # Make RPC call to user service
            if self.rpc_client:
                result = self.rpc_client.publish(
                    queue_name="user-service-queue",
                    payload=user_data,
                    response_queue_name="user-service-response-queue",
                    wait_for_response=True,
                )
                return JsonResponse({"success": True, "user_id": result.get("user_id")})
            else:
                return JsonResponse({"error": "RPC client not configured"}, status=500)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# Example worker function
def create_user_handler(user_data):
    """Example worker function that creates a user."""
    # Simulate user creation
    user_id = f"user_{hash(user_data['email']) % 10000}"
    return {"user_id": user_id, "status": "created"}


# Django Test Cases
class RPCViewTestCase(TestCase):
    """Test case for views that use RPC functionality."""

    def setUp(self):
        """Set up test environment."""
        self.rpc_manager = get_test_rpc_manager()
        self.mock_client = self.rpc_manager.get_client()
        self.mock_worker = self.rpc_manager.get_worker()

        # Set up the worker to handle user creation
        @self.mock_worker.queue("user-service-queue")
        def handle_user_creation(payload):
            return create_user_handler(payload)

    def tearDown(self):
        """Clean up after tests."""
        self.rpc_manager.clear_all()

    def test_create_user_via_rpc(self):
        """Test creating a user via RPC."""
        # Create the view and inject the mock client
        view = UserServiceView()
        view.set_rpc_client(self.mock_client)

        # Create test data
        user_data = {"name": "John Doe", "email": "john@example.com", "age": 30}

        # Make request
        request = self.client.post(
            "/api/users/", data=json.dumps(user_data), content_type="application/json"
        )

        # Check response
        self.assertEqual(request.status_code, 200)
        response_data = json.loads(request.content)
        self.assertTrue(response_data["success"])
        self.assertIn("user_id", response_data)


class RPCIntegrationTestCase(TestCase):
    """Test case for RPC integration testing."""

    @mock_rpc_for_testing()
    def test_rpc_integration(self):
        """Test RPC integration using the decorator."""
        # The decorator automatically provides self._rpc_manager
        mock_client = self._rpc_manager.get_client()
        mock_worker = self._rpc_manager.get_worker()

        # Set up worker handler
        @mock_worker.queue("test-queue")
        def test_handler(data):
            return {"processed": True, "data": data}

        # Test RPC call
        result = mock_client.publish(
            queue_name="test-queue",
            payload={"test": "data"},
            response_queue_name="response-queue",
            wait_for_response=True,
        )

        # Verify result
        self.assertIsNotNone(result)
        self.assertTrue(result["processed"])
        self.assertEqual(result["data"], {"test": "data"})


class RPCAsyncTestCase(TestCase):
    """Test case for async RPC calls."""

    def setUp(self):
        """Set up test environment."""
        self.rpc_manager = get_test_rpc_manager()
        self.mock_client = self.rpc_manager.get_client()
        self.mock_worker = self.rpc_manager.get_worker()

    def tearDown(self):
        """Clean up after tests."""
        self.rpc_manager.clear_all()

    def test_async_rpc_call(self):
        """Test async RPC call (no response expected)."""

        # Set up worker handler
        @self.mock_worker.queue("async-queue")
        def async_handler(data):
            # This would typically do some background processing
            return {"status": "processing"}

        # Make async call (no response expected)
        result = self.mock_client.publish(
            queue_name="async-queue",
            payload={"task": "background_job"},
            wait_for_response=False,  # Don't wait for response
        )

        # Should return None since we're not waiting for response
        self.assertIsNone(result)

        # Verify message was sent (check if worker processed it)
        # In a real test, you might want to add some way to verify
        # that the worker actually processed the message


# Example of how to use in Django settings for testing
class TestSettings:
    """Example Django settings for testing with RPC mocks."""

    # In your Django settings, you can configure RPC for testing
    RPC_TESTING = True
    RPC_MOCK_CLIENT = True

    @classmethod
    def get_rpc_client(cls):
        """Get RPC client based on settings."""
        if cls.RPC_TESTING and cls.RPC_MOCK_CLIENT:
            from sqs_rpc.testing import MockRPCClient

            return MockRPCClient()
        else:
            from sqs_rpc import RPCClient

            return RPCClient()


# Example Django management command for testing
class TestRPCCommand:
    """Example Django management command for testing RPC."""

    def handle(self, *args, **options):
        """Handle the management command."""
        with TestRPCManager() as rpc_manager:
            mock_client = rpc_manager.get_client()
            mock_worker = rpc_manager.get_worker()

            # Set up worker
            @mock_worker.queue("test-command-queue")
            def command_handler(data):
                return {"command_result": f"Processed: {data}"}

            # Test RPC
            result = mock_client.publish(
                queue_name="test-command-queue",
                payload={"command": "test"},
                response_queue_name="command-response-queue",
                wait_for_response=True,
            )

            print(f"RPC Test Result: {result}")


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

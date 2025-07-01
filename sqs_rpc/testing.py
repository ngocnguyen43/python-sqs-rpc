"""
Testing utilities for SQS RPC.

This module provides mock implementations of RPCClient and RPCWorker
that can be used during tests to avoid actual SQS connections.
"""

import json
import logging
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from . import exceptions

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MockRPCClient:
    """A mock RPC client for testing purposes.

    This client stores messages in memory instead of sending them to SQS.
    It can be used to test RPC functionality without requiring AWS credentials
    or actual SQS queues.
    """

    def __init__(self):
        """Initialize the mock RPC client."""
        self._messages: Dict[str, list] = {}
        self._responses: Dict[str, Any] = {}
        self._correlation_responses: Dict[str, Any] = {}

    def _get_queue_messages(self, queue_name: str) -> list:
        """Get messages for a queue, creating the queue if it doesn't exist."""
        if queue_name not in self._messages:
            self._messages[queue_name] = []
        return self._messages[queue_name]

    def publish(
        self,
        queue_name: str,
        payload: Any,
        response_queue_name: Optional[str] = None,
        wait_for_response: bool = True,
        request_attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Publish a message to a mock queue.

        Args:
            queue_name: The name of the queue to publish to
            payload: The message payload
            response_queue_name: Optional name of queue to receive responses on
            wait_for_response: Whether to wait for a response
            request_attributes: Optional additional message attributes

        Returns:
            The response payload if wait_for_response is True, None otherwise
        """
        import uuid

        correlation_id = str(uuid.uuid4())
        message_body = {"payload": payload}

        message_attributes = {
            "CorrelationId": {"DataType": "String", "StringValue": correlation_id}
        }

        if response_queue_name and wait_for_response:
            message_attributes["ReplyQueueUrl"] = {
                "DataType": "String",
                "StringValue": response_queue_name,
            }

        if request_attributes:
            message_attributes.update(request_attributes)

        # Store the message
        message = {
            "Body": json.dumps(message_body),
            "MessageAttributes": message_attributes,
            "MessageId": str(uuid.uuid4()),
            "ReceiptHandle": str(uuid.uuid4()),
        }

        queue_messages = self._get_queue_messages(queue_name)
        queue_messages.append(message)

        if not wait_for_response or not response_queue_name:
            return None

        # Wait for response
        start_time = time.time()
        timeout = 5.0  # 5 second timeout for tests

        while (time.time() - start_time) < timeout:
            if correlation_id in self._correlation_responses:
                response = self._correlation_responses.pop(correlation_id)
                if "error" in response and response["error"]:
                    err = response["error"]
                    raise exceptions.RPCProcessingError(
                        err.get("message", "Unknown processing error"),
                        error_type=err.get("type"),
                    )
                return response.get("result")
            time.sleep(0.01)

        raise exceptions.RPCRequestTimeoutError(
            f"Timeout waiting for response on {response_queue_name} for CorrelationId: {correlation_id}"
        )

    def receive_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Receive a message from a mock queue.

        Args:
            queue_name: The name of the queue to receive from

        Returns:
            The message if available, None otherwise
        """
        queue_messages = self._get_queue_messages(queue_name)
        if queue_messages:
            return queue_messages.pop(0)
        return None

    def send_response(
        self, correlation_id: str, result: Any, error: Optional[Dict[str, Any]] = None
    ):
        """Send a response for a specific correlation ID.

        Args:
            correlation_id: The correlation ID to respond to
            result: The result to send
            error: Optional error information
        """
        response = {"result": result, "error": error}
        self._correlation_responses[correlation_id] = response

    def clear_messages(self):
        """Clear all stored messages and responses."""
        self._messages.clear()
        self._correlation_responses.clear()


class MockRPCWorker:
    """A mock RPC worker for testing purposes.

    This worker processes messages from mock queues instead of actual SQS queues.
    It can be used to test worker functionality without requiring AWS credentials.
    """

    def __init__(self):
        """Initialize the mock RPC worker."""
        self._queue_handlers: Dict[str, Callable] = {}
        self._running = False
        self._threads: Dict[str, threading.Thread] = {}
        self._mock_client: Optional[MockRPCClient] = None

    def set_mock_client(self, mock_client: MockRPCClient):
        """Set the mock client to use for communication.

        Args:
            mock_client: The mock client instance
        """
        self._mock_client = mock_client

    def _process_message(self, queue_name: str, message: Dict[str, Any]):
        """Process a single message from a mock queue.

        Args:
            queue_name: The name of the queue the message came from
            message: The message to process
        """
        message_id = message["MessageId"]

        try:
            body = json.loads(message["Body"])
            payload = body.get("payload")

            if payload is None:
                raise ValueError("Message body missing 'payload'")

            handler = self._queue_handlers.get(queue_name)
            if not handler:
                raise ValueError(f"No handler registered for queue {queue_name}")

            result = handler(payload)

            # Send response if reply queue is specified
            msg_attrs = message.get("MessageAttributes", {})
            reply_queue = msg_attrs.get("ReplyQueueUrl", {}).get("StringValue")
            correlation_id = msg_attrs.get("CorrelationId", {}).get("StringValue")

            if reply_queue and correlation_id and self._mock_client:
                self._mock_client.send_response(correlation_id, result, None)

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {str(e)}")

            # Send error response if reply queue is specified
            msg_attrs = message.get("MessageAttributes", {})
            reply_queue = msg_attrs.get("ReplyQueueUrl", {}).get("StringValue")
            correlation_id = msg_attrs.get("CorrelationId", {}).get("StringValue")

            if reply_queue and correlation_id and self._mock_client:
                error_type = e.__class__.__name__
                error_info = {"type": error_type, "message": str(e)}
                self._mock_client.send_response(correlation_id, None, error_info)

    def _run_queue_worker(self, queue_name: str):
        """Run a worker thread for a specific queue.

        Args:
            queue_name: The name of the queue to process messages from
        """
        logger.info(f"Starting mock worker thread for queue {queue_name}")
        while self._running:
            if self._mock_client:
                message = self._mock_client.receive_message(queue_name)
                if message:
                    self._process_message(queue_name, message)
            time.sleep(0.01)

    def queue(self, queue_name: str):
        """Decorator to register a handler for a specific queue.

        Args:
            queue_name: The name of the queue to handle messages from

        Returns:
            A decorator function that registers the handler
        """

        def decorator(func: Callable[..., Any]):
            if queue_name in self._queue_handlers:
                raise exceptions.RPCConfigurationError(
                    f"Queue '{queue_name}' already has a handler registered"
                )

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            self._queue_handlers[queue_name] = wrapper

            # Start worker thread for this queue if not already running
            if queue_name not in self._threads:
                self._running = True
                thread = threading.Thread(
                    target=self._run_queue_worker, args=(queue_name,), daemon=True
                )
                thread.start()
                self._threads[queue_name] = thread
                logger.info(f"Started mock worker thread for queue {queue_name}")

            return wrapper

        return decorator

    def stop(self):
        """Stop all worker threads."""
        self._running = False
        for queue_name, thread in self._threads.items():
            thread.join(timeout=5)
            logger.info(f"Stopped mock worker thread for queue {queue_name}")

    def health_check(self) -> bool:
        """Check the health status of all worker threads.

        Returns:
            bool: True if all threads are running, False otherwise
        """
        if not self._running:
            logger.warning("Mock worker is not running")
            return False

        all_threads_healthy = True
        for queue_name, thread in self._threads.items():
            is_alive = thread.is_alive()
            if not is_alive:
                logger.error(
                    f"Mock worker thread for queue {queue_name} is not running"
                )
                all_threads_healthy = False
            else:
                logger.info(f"Mock worker thread for queue {queue_name} is running")

        return all_threads_healthy


class TestRPCManager:
    """A manager for testing RPC functionality.

    This class provides a convenient way to set up mock RPC clients and workers
    for testing purposes.
    """

    def __init__(self):
        """Initialize the test RPC manager."""
        self.mock_client = MockRPCClient()
        self.mock_worker = MockRPCWorker()
        self.mock_worker.set_mock_client(self.mock_client)

    def get_client(self) -> MockRPCClient:
        """Get the mock RPC client.

        Returns:
            The mock RPC client instance
        """
        return self.mock_client

    def get_worker(self) -> MockRPCWorker:
        """Get the mock RPC worker.

        Returns:
            The mock RPC worker instance
        """
        return self.mock_worker

    def clear_all(self):
        """Clear all messages and stop all workers."""
        self.mock_client.clear_messages()
        self.mock_worker.stop()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.clear_all()


# Convenience functions for Django tests
def get_test_rpc_manager() -> TestRPCManager:
    """Get a test RPC manager for Django tests.

    Returns:
        A TestRPCManager instance
    """
    return TestRPCManager()


def mock_rpc_for_testing():
    """Decorator to mock RPC functionality for tests.

    This decorator can be used on test methods to automatically
    set up mock RPC clients and workers.

    Example:
        @mock_rpc_for_testing()
        def test_my_rpc_function(self):
            # Your test code here
            pass
    """

    def decorator(test_func):
        @wraps(test_func)
        def wrapper(*args, **kwargs):
            with TestRPCManager() as rpc_manager:
                # Inject the RPC manager into the test instance if it's a method
                if args and hasattr(args[0], "_rpc_manager"):
                    args[0]._rpc_manager = rpc_manager
                return test_func(*args, **kwargs)

        return wrapper

    return decorator

import json
import logging
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

import boto3

from . import config as rpc_config
from . import exceptions

# Configure logger
logger = logging.getLogger(__name__)

T = TypeVar("T")


class RPCWorker:
    """A worker that can handle messages from multiple SQS queues."""

    def __init__(
        self,
        aws_region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        sqs_client: Optional[Any] = None,
        polling_timeout_seconds: Optional[int] = None,
    ):
        """Initialize the RPC worker.

        Args:
            aws_region_name: AWS region name
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            sqs_client: Optional pre-configured SQS client
            polling_timeout_seconds: Timeout for polling messages
        """
        if sqs_client:
            self.sqs = sqs_client
        else:
            self.sqs = boto3.client(
                "sqs",
                region_name=aws_region_name or rpc_config.AWS_REGION,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

        self.polling_timeout = (
            polling_timeout_seconds or rpc_config.DEFAULT_WORKER_POLLING_TIMEOUT_SECONDS
        )
        self._queue_handlers: Dict[str, Callable] = {}
        self._running = False
        self._queue_urls: Dict[str, str] = {}
        self._threads: Dict[str, threading.Thread] = {}

    def _get_queue_url(self, queue_name: str) -> str:
        """Get the URL for a queue by name.

        Args:
            queue_name: The name of the queue

        Returns:
            The queue URL

        Raises:
            RPCConfigurationError: If the queue doesn't exist
        """
        if queue_name not in self._queue_urls:
            try:
                response = self.sqs.get_queue_url(QueueName=queue_name)
                self._queue_urls[queue_name] = response["QueueUrl"]
            except Exception as e:
                raise exceptions.RPCConfigurationError(
                    f"Failed to get URL for queue '{queue_name}': {str(e)}"
                )
        return self._queue_urls[queue_name]

    def _process_message(self, queue_url: str, message: Dict[str, Any]):
        """Process a single message from a queue.

        Args:
            queue_url: The queue URL the message came from
            message: The SQS message to process
        """
        receipt_handle = message["ReceiptHandle"]
        message_id = message["MessageId"]

        try:
            body = json.loads(message["Body"])
            payload = body.get("payload")

            if payload is None:
                raise ValueError("Message body missing 'payload'")

            handler = self._queue_handlers.get(queue_url)
            if not handler:
                raise ValueError(f"No handler registered for queue {queue_url}")

            result = handler(payload)

            # If there's a reply queue specified, send the response
            msg_attrs = message.get("MessageAttributes", {})
            reply_queue = msg_attrs.get("ReplyQueueUrl", {}).get("StringValue")
            correlation_id = msg_attrs.get("CorrelationId", {}).get("StringValue")

            if reply_queue and correlation_id:
                response_body = {"result": result, "error": None}
                self.sqs.send_message(
                    QueueUrl=reply_queue,
                    MessageBody=json.dumps(response_body),
                    MessageAttributes={
                        "CorrelationId": {
                            "DataType": "String",
                            "StringValue": correlation_id,
                        }
                    },
                )

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {str(e)}")
            logger.debug("Traceback:", exc_info=True)

            # Send error response if reply queue is specified
            msg_attrs = message.get("MessageAttributes", {})
            reply_queue = msg_attrs.get("ReplyQueueUrl", {}).get("StringValue")
            correlation_id = msg_attrs.get("CorrelationId", {}).get("StringValue")

            if reply_queue and correlation_id:
                error_type = e.__class__.__name__
                response_body = {
                    "result": None,
                    "error": {"type": error_type, "message": str(e)},
                }
                self.sqs.send_message(
                    QueueUrl=reply_queue,
                    MessageBody=json.dumps(response_body),
                    MessageAttributes={
                        "CorrelationId": {
                            "DataType": "String",
                            "StringValue": correlation_id,
                        }
                    },
                )
        finally:
            # Always delete the processed message
            try:
                self.sqs.delete_message(
                    QueueUrl=queue_url, ReceiptHandle=receipt_handle
                )
            except Exception as delete_error:
                logger.error(f"Failed to delete message {message_id}: {delete_error}")

    def _run_queue_worker(self, queue_url: str, visibility_timeout: int = 30):
        """Run a worker thread for a specific queue.

        Args:
            queue_url: The queue URL to process messages from
            visibility_timeout: The visibility timeout for messages
        """
        logger.info(f"Starting worker thread for queue {queue_url}")
        while self._running:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=queue_url,
                    AttributeNames=["All"],
                    MessageAttributeNames=["All"],
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=self.polling_timeout,
                    VisibilityTimeout=visibility_timeout,
                )

                if "Messages" in response:
                    for message in response["Messages"]:
                        self._process_message(queue_url, message)

            except Exception as e:
                logger.error(f"Error in worker thread for queue {queue_url}: {str(e)}")
                logger.debug("Traceback:", exc_info=True)
                time.sleep(5)

    def queue(self, queue_name: str):
        """Decorator to register a handler for a specific queue.

        Args:
            queue_name: The name of the SQS queue to handle messages from

        Returns:
            A decorator function that registers the handler
        """

        def decorator(func: Callable[..., Any]):
            queue_url = self._get_queue_url(queue_name)
            if queue_url in self._queue_handlers:
                raise exceptions.RPCConfigurationError(
                    f"Queue '{queue_name}' already has a handler registered"
                )

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            self._queue_handlers[queue_url] = wrapper

            # Start worker thread for this queue if not already running
            if queue_url not in self._threads:
                self._running = True
                thread = threading.Thread(
                    target=self._run_queue_worker, args=(queue_url,), daemon=True
                )
                thread.start()
                self._threads[queue_url] = thread
                logger.info(f"Started worker thread for queue {queue_name}")

            return wrapper

        return decorator

    def stop(self):
        """Stop all worker threads."""
        self._running = False
        for queue_url, thread in self._threads.items():
            thread.join(timeout=5)
            logger.info(f"Stopped worker thread for queue {queue_url}")

    def health_check(self) -> bool:
        """Check the health status of all worker threads.

        Returns:
            bool: True if all threads are running, False otherwise
        """
        if not self._running:
            logger.warning("Worker is not running")
            return False

        all_threads_healthy = True
        for queue_url, thread in self._threads.items():
            is_alive = thread.is_alive()
            if not is_alive:
                logger.error(f"Worker thread for queue {queue_url} is not running")
                all_threads_healthy = False
            else:
                logger.info(f"Worker thread for queue {queue_url} is running")

        return all_threads_healthy

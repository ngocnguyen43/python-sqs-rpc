import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, TypeVar

import boto3

from . import config as rpc_config
from . import exceptions

# Configure logger
logger = logging.getLogger(__name__)

T = TypeVar("T")


class RPCClient:
    """A client for making RPC calls to SQS queues."""

    def __init__(
        self,
        aws_region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        sqs_client: Optional[Any] = None,
        polling_timeout_seconds: Optional[int] = None,
        max_wait_time_seconds: Optional[int] = None,
    ):
        """Initialize the RPC client.

        Args:
            aws_region_name: AWS region name
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            sqs_client: Optional pre-configured SQS client
            polling_timeout_seconds: Timeout for polling messages
            max_wait_time_seconds: Maximum time to wait for responses
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
            polling_timeout_seconds or rpc_config.DEFAULT_CLIENT_POLLING_TIMEOUT_SECONDS
        )
        self.max_wait_time = (
            max_wait_time_seconds or rpc_config.DEFAULT_CLIENT_MAX_WAIT_TIME_SECONDS
        )
        self._queue_urls: Dict[str, str] = {}

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

    def publish(
        self,
        queue_name: str,
        payload: Any,
        response_queue_name: Optional[str] = None,
        wait_for_response: bool = True,
        request_attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Publish a message to a queue and optionally wait for a response.

        Args:
            queue_name: The name of the SQS queue to publish to
            payload: The message payload
            response_queue_name: Optional name of queue to receive responses on
            wait_for_response: Whether to wait for a response
            request_attributes: Optional additional SQS message attributes

        Returns:
            The response payload if wait_for_response is True, None otherwise

        Raises:
            RPCRequestTimeoutError: If no response received within max_wait_time
            RPCProcessingError: If the worker returns an error
            SQSRPCError: For SQS communication issues
        """
        queue_url = self._get_queue_url(queue_name)
        response_queue_url = (
            self._get_queue_url(response_queue_name) if response_queue_name else None
        )

        correlation_id = str(uuid.uuid4())
        message_body = {"payload": payload}

        message_attributes = {
            "CorrelationId": {"DataType": "String", "StringValue": correlation_id}
        }

        # Only set ReplyQueueUrl if we want a response
        if wait_for_response and response_queue_url:
            message_attributes["ReplyQueueUrl"] = {
                "DataType": "String",
                "StringValue": response_queue_url,
            }

        if request_attributes:
            message_attributes.update(request_attributes)

        try:
            self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes=message_attributes,
            )
        except Exception as e:
            raise exceptions.SQSRPCError(f"Failed to send message to SQS: {str(e)}")

        if not wait_for_response or not response_queue_url:
            return None

        start_time = time.time()
        while (time.time() - start_time) < self.max_wait_time:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=response_queue_url,
                    MessageAttributeNames=["CorrelationId"],
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=self.polling_timeout,
                )

                if "Messages" in response:
                    for message in response["Messages"]:
                        msg_attrs = message.get("MessageAttributes", {})
                        msg_correlation_id = msg_attrs.get("CorrelationId", {}).get(
                            "StringValue"
                        )
                        receipt_handle = message["ReceiptHandle"]

                        if msg_correlation_id == correlation_id:
                            try:
                                response_body = json.loads(message["Body"])
                            except json.JSONDecodeError as e:
                                self.sqs.delete_message(
                                    QueueUrl=response_queue_url,
                                    ReceiptHandle=receipt_handle,
                                )
                                raise exceptions.RPCProcessingError(
                                    f"Invalid JSON response: {str(e)}"
                                )

                            self.sqs.delete_message(
                                QueueUrl=response_queue_url,
                                ReceiptHandle=receipt_handle,
                            )

                            if "error" in response_body and response_body["error"]:
                                err = response_body["error"]
                                raise exceptions.RPCProcessingError(
                                    err.get("message", "Unknown processing error"),
                                    error_type=err.get("type"),
                                )
                            return response_body.get("result")
                        else:
                            # Make message visible again for other clients
                            try:
                                self.sqs.change_message_visibility(
                                    QueueUrl=response_queue_url,
                                    ReceiptHandle=receipt_handle,
                                    VisibilityTimeout=0,
                                )
                            except Exception:
                                logger.warning(
                                    f"Could not change visibility for message {message['MessageId']}"
                                )

            except Exception as e:
                raise exceptions.SQSRPCError(
                    f"Failed to receive message from SQS: {str(e)}"
                )

        raise exceptions.RPCRequestTimeoutError(
            f"Timeout waiting for response on {response_queue_name} for CorrelationId: {correlation_id}"
        )

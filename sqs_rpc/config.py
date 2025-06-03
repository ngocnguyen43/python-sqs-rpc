# sqs_rpc_module/config.py
import os

# Default AWS Region (can be overridden)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Default SQS Queue URLs (MUST be configured by the application)
# These are placeholders; the application using this module should set them.
DEFAULT_REQUEST_QUEUE_URL = None
DEFAULT_RESPONSE_QUEUE_URL = (
    None  # Used by the client to listen for its specific responses
)

# Default timeouts for the client
DEFAULT_CLIENT_POLLING_TIMEOUT_SECONDS = (
    5  # SQS long polling timeout for each receive_message call
)
DEFAULT_CLIENT_MAX_WAIT_TIME_SECONDS = (
    30  # Total time the client will wait for a response
)

# Default timeouts for the worker
DEFAULT_WORKER_POLLING_TIMEOUT_SECONDS = (
    10  # SQS long polling for worker receiving requests
)

# Boto3 SQS client (can be None, and created on demand or passed in)
SQS_CLIENT = None

# Example of how you might integrate with Django settings if this module is part of a Django app
# Or, the client/worker instances can be configured directly when instantiated.
# try:
#     from django.conf import settings
#     AWS_REGION = getattr(settings, 'SQS_RPC_AWS_REGION', AWS_REGION)
#     DEFAULT_REQUEST_QUEUE_URL = getattr(settings, 'SQS_RPC_REQUEST_QUEUE_URL', None)
#     DEFAULT_RESPONSE_QUEUE_URL = getattr(settings, 'SQS_RPC_RESPONSE_QUEUE_URL', None)
#     # etc.
# except ImportError:
#     pass # Django not available or settings not configured

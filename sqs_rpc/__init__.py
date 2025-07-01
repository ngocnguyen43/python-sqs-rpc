"""
SQS RPC - A simple RPC implementation using AWS SQS.

This package provides a simple way to implement RPC-style communication
using AWS SQS queues. It supports both synchronous and asynchronous
message handling with a clean, decorator-based API.
"""

from . import exceptions
from .client import RPCClient
from .worker import RPCWorker

# Import testing utilities
try:
    from . import testing

    __all__ = ["RPCWorker", "RPCClient", "exceptions", "testing"]
except ImportError:
    __all__ = ["RPCWorker", "RPCClient", "exceptions"]

__version__ = "0.0.1"

class SQSRPCError(Exception):
    """Base exception for SQS RPC errors."""

    pass


class RPCRequestTimeoutError(SQSRPCError):
    """Raised when waiting for an RPC response times out."""

    pass


class RPCProcessingError(SQSRPCError):
    """Raised when an error occurs during RPC method execution on the worker."""

    def __init__(self, message, error_type=None):
        super().__init__(message)
        self.error_type = error_type


class RPCConfigurationError(SQSRPCError):
    """Raised for configuration-related errors."""

    pass

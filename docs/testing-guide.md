# SQS RPC Testing Utilities

This document explains how to use the testing utilities provided by `sqs_rpc` to test your Django applications without requiring actual AWS SQS connections.

## Overview

The testing utilities provide mock implementations of `RPCClient` and `RPCWorker` that store messages in memory instead of sending them to actual SQS queues. This allows you to:

- Run tests without AWS credentials
- Test RPC functionality in isolation
- Avoid costs associated with SQS usage during testing
- Speed up test execution

## Quick Start

### Basic Usage

```python
from sqs_rpc.testing import TestRPCManager

# Use as a context manager
with TestRPCManager() as rpc_manager:
    mock_client = rpc_manager.get_client()
    mock_worker = rpc_manager.get_worker()
    
    # Set up worker handler
    @mock_worker.queue('test-queue')
    def test_handler(data):
        return {'processed': True, 'data': data}
    
    # Test RPC call
    result = mock_client.publish(
        queue_name='test-queue',
        payload={'test': 'data'},
        response_queue_name='response-queue',
        wait_for_response=True
    )
    
    print(f"Result: {result}")
```

### Django Test Case Example

```python
from django.test import TestCase
from sqs_rpc.testing import get_test_rpc_manager

class MyRPCTestCase(TestCase):
    def setUp(self):
        self.rpc_manager = get_test_rpc_manager()
        self.mock_client = self.rpc_manager.get_client()
        self.mock_worker = self.rpc_manager.get_worker()
        
        # Set up worker handlers
        @self.mock_worker.queue('user-service-queue')
        def create_user(data):
            return {'user_id': f"user_{hash(data['email'])}"}
    
    def tearDown(self):
        self.rpc_manager.clear_all()
    
    def test_user_creation(self):
        result = self.mock_client.publish(
            queue_name='user-service-queue',
            payload={'email': 'test@example.com'},
            response_queue_name='response-queue',
            wait_for_response=True
        )
        
        self.assertIn('user_id', result)
```

## Available Classes and Functions

### TestRPCManager

The main class for managing mock RPC clients and workers.

```python
from sqs_rpc.testing import TestRPCManager

rpc_manager = TestRPCManager()
mock_client = rpc_manager.get_client()
mock_worker = rpc_manager.get_worker()
rpc_manager.clear_all()  # Clean up
```

### MockRPCClient

A mock implementation of `RPCClient` that stores messages in memory.

```python
from sqs_rpc.testing import MockRPCClient

client = MockRPCClient()

# Same API as real RPCClient
result = client.publish(
    queue_name='test-queue',
    payload={'data': 'test'},
    response_queue_name='response-queue',
    wait_for_response=True
)
```

### MockRPCWorker

A mock implementation of `RPCWorker` that processes messages from mock queues.

```python
from sqs_rpc.testing import MockRPCWorker

worker = MockRPCWorker()

@worker.queue('test-queue')
def handler(data):
    return {'result': f"Processed: {data}"}
```

### Decorator for Tests

Use the `@mock_rpc_for_testing()` decorator to automatically set up mock RPC for test methods.

```python
from sqs_rpc.testing import mock_rpc_for_testing

class MyTestCase(TestCase):
    @mock_rpc_for_testing()
    def test_with_rpc(self):
        # self._rpc_manager is automatically available
        mock_client = self._rpc_manager.get_client()
        # ... your test code
```

## Integration with Django

### Django Settings

You can configure your Django settings to use mock RPC during testing:

```python
# settings.py
import os

if os.environ.get('DJANGO_TESTING'):
    RPC_TESTING = True
    RPC_MOCK_CLIENT = True
else:
    RPC_TESTING = False
    RPC_MOCK_CLIENT = False

# In your application code
def get_rpc_client():
    if settings.RPC_TESTING and settings.RPC_MOCK_CLIENT:
        from sqs_rpc.testing import MockRPCClient
        return MockRPCClient()
    else:
        from sqs_rpc import RPCClient
        return RPCClient()
```

### Django Views

Inject mock clients into your Django views for testing:

```python
from django.views import View
from sqs_rpc.testing import MockRPCClient

class MyView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rpc_client = None
    
    def set_rpc_client(self, client):
        self.rpc_client = client
    
    def post(self, request):
        if self.rpc_client:
            result = self.rpc_client.publish(
                queue_name='service-queue',
                payload=request.data,
                response_queue_name='response-queue',
                wait_for_response=True
            )
            return JsonResponse(result)

# In your test
def test_my_view(self):
    view = MyView()
    view.set_rpc_client(MockRPCClient())
    # ... test the view
```

## Testing Patterns

### Testing Synchronous RPC Calls

```python
def test_sync_rpc(self):
    with TestRPCManager() as rpc_manager:
        mock_client = rpc_manager.get_client()
        mock_worker = rpc_manager.get_worker()
        
        @mock_worker.queue('test-queue')
        def handler(data):
            return {'result': data['value'] * 2}
        
        result = mock_client.publish(
            queue_name='test-queue',
            payload={'value': 5},
            response_queue_name='response-queue',
            wait_for_response=True
        )
        
        self.assertEqual(result['result'], 10)
```

### Testing Asynchronous RPC Calls

```python
def test_async_rpc(self):
    with TestRPCManager() as rpc_manager:
        mock_client = rpc_manager.get_client()
        mock_worker = rpc_manager.get_worker()
        
        @mock_worker.queue('async-queue')
        def async_handler(data):
            # Background processing
            return {'status': 'processing'}
        
        # Don't wait for response
        result = mock_client.publish(
            queue_name='async-queue',
            payload={'task': 'background_job'},
            wait_for_response=False
        )
        
        self.assertIsNone(result)  # No response expected
```

### Testing Error Handling

```python
def test_rpc_error(self):
    with TestRPCManager() as rpc_manager:
        mock_client = rpc_manager.get_client()
        mock_worker = rpc_manager.get_worker()
        
        @mock_worker.queue('error-queue')
        def error_handler(data):
            raise ValueError("Test error")
        
        with self.assertRaises(exceptions.RPCProcessingError):
            mock_client.publish(
                queue_name='error-queue',
                payload={'test': 'data'},
                response_queue_name='response-queue',
                wait_for_response=True
            )
```

## Best Practices

1. **Always clean up**: Use `rpc_manager.clear_all()` in `tearDown()` or use context managers.

2. **Isolate tests**: Each test should have its own mock client and worker to avoid interference.

3. **Test both success and error cases**: Make sure your error handling works correctly.

4. **Use meaningful queue names**: Use descriptive queue names in your tests to make them more readable.

5. **Test async calls**: Don't forget to test cases where `wait_for_response=False`.

## Limitations

- The mock implementations store messages in memory, so they don't persist between test runs.
- They don't simulate network delays or SQS-specific behaviors.
- They don't test actual AWS integration.

For integration testing with real SQS, you should use separate test cases with actual AWS credentials and test queues. 
# SQS RPC

A Python library for Remote Procedure Call (RPC) communication using Amazon SQS queues.

## 🚀 Quick Start

```python
from sqs_rpc import RPCClient, RPCWorker

# Client
client = RPCClient()
result = client.publish(
    queue_name='my-service',
    payload={'data': 'test'},
    response_queue_name='response-queue',
    wait_for_response=True
)

# Worker
worker = RPCWorker()

@worker.queue('my-service')
def handle_request(data):
    return {'result': f"Processed: {data}"}
```

## 📚 Documentation

📖 **Complete documentation is available in the [docs/](docs/) folder:**

- **[Quick Start Guide](docs/quickstart.md)** - Get up and running in minutes
- **[Django Integration](docs/django-integration.md)** - Using SQS RPC with Django
- **[Testing Guide](docs/testing-guide.md)** - Testing with mocks and utilities
- **[API Reference](docs/api/)** - Complete API documentation
- **[Examples](docs/examples/)** - Code examples and patterns

## 🧪 Testing

SQS RPC includes comprehensive testing utilities for Django and other frameworks:

```python
from sqs_rpc.testing import TestRPCManager

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
    
    assert result['result'] == 10
```

## 📦 Installation

```bash
pip install sqs-rpc
```

## 🔧 Features

- **Simple RPC Communication**: Easy-to-use client and worker classes
- **Synchronous & Asynchronous**: Support for both sync and async RPC calls
- **Django Integration**: Seamless integration with Django applications
- **Testing Support**: Comprehensive testing utilities with mocks
- **Error Handling**: Robust error handling and recovery
- **Performance**: Optimized for high-throughput scenarios

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/contributing.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
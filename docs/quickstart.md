# Quick Start Guide

Get up and running with SQS RPC in minutes. This guide will walk you through the basic setup and usage.

## 📦 Installation

Install SQS RPC using pip:

```bash
pip install sqs-rpc
```

## 🔧 Basic Setup

### 1. Configure AWS Credentials

Make sure you have AWS credentials configured. You can do this in several ways:

**Option A: AWS CLI**
```bash
aws configure
```

**Option B: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option C: IAM Roles** (if running on EC2 or ECS)

### 2. Create SQS Queues

Create the queues you'll need for your RPC communication:

```bash
# Create request queue
aws sqs create-queue --queue-name my-service-queue

# Create response queue
aws sqs create-queue --queue-name my-service-response-queue
```

## 🚀 Basic Usage

### Simple RPC Client

```python
from sqs_rpc import RPCClient

# Initialize client
client = RPCClient()

# Make an RPC call
result = client.publish(
    queue_name='my-service-queue',
    payload={'message': 'Hello, World!'},
    response_queue_name='my-service-response-queue',
    wait_for_response=True
)

print(f"Response: {result}")
```

### Simple RPC Worker

```python
from sqs_rpc import RPCWorker

# Initialize worker
worker = RPCWorker()

# Define a handler function
@worker.queue('my-service-queue')
def handle_message(data):
    message = data.get('message', '')
    return {'response': f"Echo: {message}"}

# Start the worker (this will run indefinitely)
try:
    # Keep the worker running
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    worker.stop()
```

## 🔄 Complete Example

Here's a complete example showing both client and worker:

### Worker Script (`worker.py`)

```python
from sqs_rpc import RPCWorker

worker = RPCWorker()

@worker.queue('calculator-queue')
def add_numbers(data):
    a = data.get('a', 0)
    b = data.get('b', 0)
    return {'result': a + b}

@worker.queue('calculator-queue')
def multiply_numbers(data):
    a = data.get('a', 0)
    b = data.get('b', 0)
    return {'result': a * b}

if __name__ == '__main__':
    print("Starting calculator worker...")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping worker...")
        worker.stop()
```

### Client Script (`client.py`)

```python
from sqs_rpc import RPCClient

client = RPCClient()

# Test addition
result = client.publish(
    queue_name='calculator-queue',
    payload={'a': 5, 'b': 3},
    response_queue_name='calculator-response-queue',
    wait_for_response=True
)

print(f"5 + 3 = {result['result']}")

# Test multiplication
result = client.publish(
    queue_name='calculator-queue',
    payload={'a': 4, 'b': 7},
    response_queue_name='calculator-response-queue',
    wait_for_response=True
)

print(f"4 * 7 = {result['result']}")
```

### Running the Example

1. **Start the worker** in one terminal:
   ```bash
   python worker.py
   ```

2. **Run the client** in another terminal:
   ```bash
   python client.py
   ```

## 🧪 Testing with Mocks

For testing without AWS, use the testing utilities:

```python
from sqs_rpc.testing import TestRPCManager

def test_calculator():
    with TestRPCManager() as rpc_manager:
        mock_client = rpc_manager.get_client()
        mock_worker = rpc_manager.get_worker()
        
        @mock_worker.queue('calculator-queue')
        def add_numbers(data):
            return {'result': data['a'] + data['b']}
        
        result = mock_client.publish(
            queue_name='calculator-queue',
            payload={'a': 10, 'b': 20},
            response_queue_name='response-queue',
            wait_for_response=True
        )
        
        assert result['result'] == 30
```

## 🔧 Configuration Options

You can customize the client and worker behavior:

```python
from sqs_rpc import RPCClient, RPCWorker

# Client with custom settings
client = RPCClient(
    aws_region_name='us-west-2',
    polling_timeout_seconds=20,
    max_wait_time_seconds=60
)

# Worker with custom settings
worker = RPCWorker(
    aws_region_name='us-west-2',
    polling_timeout_seconds=20
)
```

## 📋 Next Steps

- Read the [Client Usage Guide](client-usage.md) for detailed client options
- Check the [Worker Implementation Guide](worker-implementation.md) for advanced worker patterns
- Explore [Testing Guide](testing-guide.md) for comprehensive testing strategies
- See [Django Integration](django-integration.md) for web framework integration

## 🆘 Need Help?

- Check the [Error Handling Guide](error-handling.md) for common issues
- Review the [API Reference](api/) for complete documentation
- Look at [Examples](examples/) for more use cases 
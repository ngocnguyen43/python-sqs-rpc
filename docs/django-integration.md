# Django Integration Guide

This guide shows how to integrate SQS RPC with Django applications, including best practices for testing and production deployment.

## 🚀 Quick Integration

### Basic Django View with RPC

```python
from django.http import JsonResponse
from django.views import View
from sqs_rpc import RPCClient

class UserServiceView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rpc_client = RPCClient()
    
    def post(self, request):
        try:
            user_data = {
                'name': request.POST.get('name'),
                'email': request.POST.get('email'),
                'age': request.POST.get('age')
            }
            
            # Make RPC call to user service
            result = self.rpc_client.publish(
                queue_name='user-service-queue',
                payload=user_data,
                response_queue_name='user-service-response-queue',
                wait_for_response=True
            )
            
            return JsonResponse({
                'success': True,
                'user_id': result.get('user_id')
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)
```

## 🔧 Django Settings Configuration

### Environment-Based Configuration

```python
# settings.py
import os
from sqs_rpc import RPCClient

# RPC Configuration
RPC_CONFIG = {
    'aws_region_name': os.environ.get('AWS_REGION', 'us-east-1'),
    'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
    'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
    'polling_timeout_seconds': int(os.environ.get('RPC_POLLING_TIMEOUT', 20)),
    'max_wait_time_seconds': int(os.environ.get('RPC_MAX_WAIT_TIME', 60)),
}

# Create RPC client instance
rpc_client = RPCClient(**RPC_CONFIG)
```

### Testing Configuration

```python
# settings_test.py
from .settings import *

# Use mock RPC for testing
RPC_TESTING = True
RPC_MOCK_CLIENT = True

# Disable actual AWS calls during tests
AWS_ACCESS_KEY_ID = None
AWS_SECRET_ACCESS_KEY = None
```

## 🏗️ Django App Structure

### Recommended Project Structure

```
myproject/
├── manage.py
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── myapp/
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── services.py
│   ├── workers.py
│   └── tests.py
└── workers/
    ├── __init__.py
    ├── user_worker.py
    └── notification_worker.py
```

### Service Layer Pattern

```python
# myapp/services.py
from django.conf import settings
from sqs_rpc import RPCClient

class UserService:
    def __init__(self):
        self.rpc_client = getattr(settings, 'rpc_client', RPCClient())
    
    def create_user(self, user_data):
        """Create user via RPC call."""
        return self.rpc_client.publish(
            queue_name='user-service-queue',
            payload=user_data,
            response_queue_name='user-service-response-queue',
            wait_for_response=True
        )
    
    def send_notification(self, notification_data):
        """Send notification asynchronously."""
        return self.rpc_client.publish(
            queue_name='notification-queue',
            payload=notification_data,
            wait_for_response=False  # Async notification
        )

# Usage in views
from .services import UserService

class UserView(View):
    def post(self, request):
        user_service = UserService()
        result = user_service.create_user(request.data)
        return JsonResponse(result)
```

## 🧪 Testing with Django

### Test Case with Mock RPC

```python
# myapp/tests.py
from django.test import TestCase
from django.urls import reverse
from sqs_rpc.testing import get_test_rpc_manager
from .services import UserService

class UserServiceTestCase(TestCase):
    def setUp(self):
        self.rpc_manager = get_test_rpc_manager()
        self.mock_client = self.rpc_manager.get_client()
        self.mock_worker = self.rpc_manager.get_worker()
        
        # Set up worker handlers
        @self.mock_worker.queue('user-service-queue')
        def create_user_handler(data):
            return {'user_id': f"user_{hash(data['email'])}"}
    
    def tearDown(self):
        self.rpc_manager.clear_all()
    
    def test_create_user(self):
        # Inject mock client into service
        user_service = UserService()
        user_service.rpc_client = self.mock_client
        
        # Test user creation
        result = user_service.create_user({
            'name': 'John Doe',
            'email': 'john@example.com',
            'age': 30
        })
        
        self.assertIn('user_id', result)
```

### View Testing

```python
# myapp/tests.py
from django.test import TestCase
from django.urls import reverse
from sqs_rpc.testing import get_test_rpc_manager

class UserViewTestCase(TestCase):
    def setUp(self):
        self.rpc_manager = get_test_rpc_manager()
        self.mock_client = self.rpc_manager.get_client()
        self.mock_worker = self.rpc_manager.get_worker()
        
        @self.mock_worker.queue('user-service-queue')
        def create_user_handler(data):
            return {'user_id': 'test_user_123'}
    
    def tearDown(self):
        self.rpc_manager.clear_all()
    
    def test_create_user_view(self):
        # Mock the RPC client in settings
        from django.conf import settings
        settings.rpc_client = self.mock_client
        
        response = self.client.post(reverse('create_user'), {
            'name': 'John Doe',
            'email': 'john@example.com',
            'age': 30
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('user_id', data)
```

### Using the Decorator Pattern

```python
# myapp/tests.py
from django.test import TestCase
from sqs_rpc.testing import mock_rpc_for_testing

class UserViewTestCase(TestCase):
    @mock_rpc_for_testing()
    def test_create_user_with_decorator(self):
        # self._rpc_manager is automatically available
        mock_client = self._rpc_manager.get_client()
        mock_worker = self._rpc_manager.get_worker()
        
        @mock_worker.queue('user-service-queue')
        def create_user_handler(data):
            return {'user_id': 'test_user_123'}
        
        # Test your view or service
        # ...
```

## 🔄 Django Management Commands

### RPC Worker Management Command

```python
# myapp/management/commands/run_rpc_worker.py
from django.core.management.base import BaseCommand
from sqs_rpc import RPCWorker
from myapp.workers import user_worker, notification_worker

class Command(BaseCommand):
    help = 'Run RPC workers for the application'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--worker-type',
            type=str,
            choices=['user', 'notification', 'all'],
            default='all',
            help='Type of worker to run'
        )
    
    def handle(self, *args, **options):
        worker_type = options['worker_type']
        
        if worker_type in ['user', 'all']:
            self.stdout.write('Starting user worker...')
            user_worker.start()
        
        if worker_type in ['notification', 'all']:
            self.stdout.write('Starting notification worker...')
            notification_worker.start()
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('Stopping workers...')
            if worker_type in ['user', 'all']:
                user_worker.stop()
            if worker_type in ['notification', 'all']:
                notification_worker.stop()
```

### Worker Implementation

```python
# myapp/workers.py
from sqs_rpc import RPCWorker
from django.conf import settings

# User service worker
user_worker = RPCWorker(
    aws_region_name=settings.RPC_CONFIG['aws_region_name'],
    aws_access_key_id=settings.RPC_CONFIG['aws_access_key_id'],
    aws_secret_access_key=settings.RPC_CONFIG['aws_secret_access_key'],
)

@user_worker.queue('user-service-queue')
def create_user_handler(data):
    from .models import User
    
    user = User.objects.create(
        name=data['name'],
        email=data['email'],
        age=data['age']
    )
    
    return {'user_id': user.id, 'status': 'created'}

# Notification worker
notification_worker = RPCWorker(
    aws_region_name=settings.RPC_CONFIG['aws_region_name'],
    aws_access_key_id=settings.RPC_CONFIG['aws_access_key_id'],
    aws_secret_access_key=settings.RPC_CONFIG['aws_secret_access_key'],
)

@notification_worker.queue('notification-queue')
def send_notification_handler(data):
    # Send notification logic
    return {'status': 'sent', 'recipient': data['email']}
```

## 🚀 Production Deployment

### Using Celery for Worker Management

```python
# myapp/celery.py
from celery import Celery
from django.conf import settings
from sqs_rpc import RPCWorker

app = Celery('myapp')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Initialize RPC workers
user_worker = RPCWorker(
    aws_region_name=settings.RPC_CONFIG['aws_region_name'],
    aws_access_key_id=settings.RPC_CONFIG['aws_access_key_id'],
    aws_secret_access_key=settings.RPC_CONFIG['aws_secret_access_key'],
)

@app.on_after_configure.connect
def setup_rpc_workers(sender, **kwargs):
    # Start RPC workers when Celery starts
    user_worker.start()
```

### Environment Variables

```bash
# .env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
RPC_POLLING_TIMEOUT=20
RPC_MAX_WAIT_TIME=60
```

### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run Django with RPC workers
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## 🔒 Security Considerations

### IAM Permissions

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueUrl",
                "sqs:ChangeMessageVisibility"
            ],
            "Resource": [
                "arn:aws:sqs:*:*:user-service-queue",
                "arn:aws:sqs:*:*:user-service-response-queue",
                "arn:aws:sqs:*:*:notification-queue"
            ]
        }
    ]
}
```


## 📊 Monitoring and Logging

### Django Logging Configuration

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'sqs_rpc': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## 🔧 Best Practices

1. **Use Service Layer**: Separate RPC logic from views
2. **Environment Configuration**: Use environment variables for AWS credentials
3. **Testing**: Always use mocks for testing
4. **Error Handling**: Implement proper error handling and logging
5. **Monitoring**: Set up monitoring for RPC calls and worker health
6. **Security**: Use IAM roles and proper permissions
7. **Performance**: Configure appropriate timeouts and polling intervals

## 📚 Next Steps

- Read the [Testing Guide](testing-guide.md) for comprehensive testing strategies
- Check the [Performance Guide](performance.md) for optimization tips
- Explore [Error Handling](error-handling.md) for robust error management
- See [API Reference](api/) for complete documentation 
# Quick Start Guide

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Virtual environment (recommended)

## Initial Setup

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables

```bash
cp env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `SECRET_KEY` - Django secret key
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL credentials
- `REDIS_URL` - Redis connection URL
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY` - Stripe API keys (optional for testing)
- `SSLCOMMERZ_STORE_ID`, `SSLCOMMERZ_STORE_PASSWORD` - SSLCommerz credentials (optional)

### 4. Database Setup

```bash
# Create database migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

### 6. Run Celery Worker (Optional - for background tasks)

In a separate terminal:

```bash
celery -A config worker -l info
```

### 7. Run Celery Beat (Optional - for scheduled tasks)

In a separate terminal:

```bash
celery -A config beat -l info
```

## Using Makefile

Alternatively, use the Makefile commands:

```bash
make install          # Install dependencies
make migrate          # Run migrations
make createsuperuser  # Create superuser
make runserver        # Run development server
make celery           # Run Celery worker
make celery-beat      # Run Celery beat
make test             # Run tests
```

## Testing the API

### 1. Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "password2": "securepassword123",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "My Company"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

Save the `access` token from the response.

### 3. Create a Client

```bash
curl -X POST http://localhost:8000/api/clients/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ABC Company",
    "email": "client@example.com",
    "phone": "+1234567890",
    "company": "ABC Corp"
  }'
```

### 4. Create an Invoice

```bash
curl -X POST http://localhost:8000/api/invoices/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client": 1,
    "invoice_number": "INV-20240101-1-ABC123",
    "issue_date": "2024-01-01",
    "due_date": "2024-01-31",
    "status": "DRAFT",
    "currency": "USD",
    "items": [
      {
        "title": "Website Development",
        "description": "Custom website development",
        "quantity": 1,
        "unit_price": "1000.00",
        "tax_rate": "10.00"
      }
    ]
  }'
```

## Admin Panel

Access Django admin at `http://localhost:8000/admin/` using your superuser credentials.

## Next Steps

1. Configure payment gateways (Stripe/SSLCommerz) in `.env`
2. Set up email configuration for notifications
3. Configure Celery Beat schedules for automated reminders
4. Set up frontend to consume the API
5. Deploy to production (use `config.settings.production`)

## Troubleshooting

### Database Connection Error
- Ensure PostgreSQL is running
- Check database credentials in `.env`
- Verify database exists: `createdb invoiceflow`

### Redis Connection Error
- Ensure Redis is running: `redis-server`
- Check Redis URL in `.env`

### Celery Not Working
- Ensure Redis is running
- Check `CELERY_BROKER_URL` in settings
- Verify Celery is installed: `pip install celery`

### Import Errors
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

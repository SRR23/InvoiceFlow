# InvoiceFlow - SaaS Invoice & Billing Platform

A production-ready Django REST Framework backend for a SaaS invoice and billing platform with Stripe and SSLCommerz payment integrations.

## Features

- ✅ User authentication with JWT (email/password and Google OAuth)
- ✅ Client management
- ✅ Invoice creation and management
- ✅ Invoice items with tax calculation
- ✅ Public invoice links for clients
- ✅ Payment processing (Stripe & SSLCommerz)
- ✅ Webhook handling for payment gateways
- ✅ Analytics and dashboard stats
- ✅ Email notifications via Celery
- ✅ Redis caching
- ✅ Scheduled tasks (Celery Beat)
- ✅ Separate settings for development and production

## Tech Stack

- **Framework**: Django 5.0+ with Django REST Framework
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Database**: PostgreSQL
- **Cache**: Redis
- **Task Queue**: Celery with Redis broker
- **Payment Gateways**: Stripe, SSLCommerz
- **API**: RESTful API with DRF

## Project Structure

```
invoice_saas/
│
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── development.py   # Development settings
│   │   └── production.py    # Production settings
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
│
├── apps/
│   ├── accounts/            # User authentication & profiles
│   ├── clients/            # Client management
│   ├── invoices/           # Invoice & invoice items
│   ├── payments/           # Payment processing
│   ├── analytics/          # Dashboard & analytics
│   └── notifications/      # Email notifications (Celery tasks)
│
├── utils/
│   ├── helpers.py          # Helper functions
│   ├── permissions.py      # Custom permissions
│   ├── constants.py        # App constants
│   └── exceptions.py       # Exception handlers
│
├── requirements/
│   ├── base.txt            # Base dependencies
│   ├── development.txt     # Dev dependencies
│   └── production.txt      # Production dependencies
│
├── manage.py
└── requirements.txt
```

## Setup Instructions

### 1. Clone and Setup Virtual Environment

```bash
cd InvoiceFlow
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:
- Database credentials
- Redis URL
- Stripe keys
- SSLCommerz credentials
- Email settings

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

### 6. Run Celery Worker (in separate terminal)

```bash
celery -A config worker -l info
```

### 7. Run Celery Beat (for scheduled tasks, in separate terminal)

```bash
celery -A config beat -l info
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/google-login/` - Google OAuth login
- `POST /api/auth/logout/` - User logout
- `POST /api/auth/token/refresh/` - Refresh JWT token
- `GET /api/auth/profile/` - Get user profile

### Clients
- `GET /api/clients/` - List clients
- `POST /api/clients/` - Create client
- `GET /api/clients/{id}/` - Get client
- `PATCH /api/clients/{id}/` - Update client
- `DELETE /api/clients/{id}/` - Delete client

### Invoices
- `GET /api/invoices/` - List invoices
- `POST /api/invoices/` - Create invoice
- `GET /api/invoices/{id}/` - Get invoice
- `PATCH /api/invoices/{id}/` - Update invoice
- `DELETE /api/invoices/{id}/` - Delete invoice
- `POST /api/invoices/{id}/send_email/` - Send invoice email
- `POST /api/invoices/{id}/mark_sent/` - Mark invoice as sent
- `POST /api/invoices/{id}/cancel/` - Cancel invoice

### Invoice Items
- `GET /api/invoices/items/` - List invoice items
- `POST /api/invoices/items/` - Create invoice item
- `GET /api/invoices/items/{id}/` - Get invoice item
- `PATCH /api/invoices/items/{id}/` - Update invoice item
- `DELETE /api/invoices/items/{id}/` - Delete invoice item

### Public Invoice
- `GET /api/public/invoice/{public_id}/` - View public invoice (no auth required)

### Payments
- `GET /api/payments/` - List payments
- `POST /api/payments/stripe/create/` - Create Stripe payment
- `POST /api/payments/sslcommerz/create/` - Create SSLCommerz payment
- `POST /api/payments/webhooks/stripe/` - Stripe webhook
- `POST /api/payments/webhooks/sslcommerz/` - SSLCommerz webhook

### Analytics
- `GET /api/analytics/dashboard/` - Get dashboard stats
- `GET /api/analytics/revenue/` - Get revenue report

## Models

### User (Custom)
- Email-based authentication
- Google OAuth support
- Business user flag (`is_business_user`)

### Client
- Belongs to a business user
- Stores customer information

### Invoice
- Belongs to a business user and client
- Has invoice items
- Public UUID for sharing
- Status: DRAFT, SENT, PAID, OVERDUE, CANCELLED

### InvoiceItem
- Belongs to an invoice
- Quantity, unit price, tax rate
- Auto-calculates totals

### Payment
- Belongs to an invoice
- Supports Stripe and SSLCommerz
- Tracks transaction status

### WebhookEvent
- Logs payment gateway webhooks
- Helps with debugging

## Permissions

- **IsBusinessUser**: Only business users can access business APIs
- **IsOwner**: Users can only access their own resources

## Celery Tasks

- `send_invoice_email` - Send invoice to client
- `send_payment_receipt` - Send payment confirmation
- `send_due_invoice_reminder` - Daily reminder for due invoices
- `generate_invoice_pdf` - Generate invoice PDF

## Scheduled Jobs (Celery Beat)

- Daily: Check overdue invoices and send reminders
- Weekly: Send revenue summary (can be configured)

## Caching

Redis is used for caching:
- Dashboard stats (10 minutes TTL)
- Recent invoices (5 minutes TTL)
- Client lists (5 minutes TTL)

## Development vs Production

- **Development**: Uses `config.settings.development`
- **Production**: Uses `config.settings.production`

Set `DJANGO_SETTINGS_MODULE` environment variable or update `manage.py` to switch.

## Testing

```bash
pytest
```

## License

MIT

## Author

InvoiceFlow Development Team

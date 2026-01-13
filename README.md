# OTT Compliance Events Pipeline

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An event collection and analysis pipeline for Smart TV/OTT platforms, including a compliance risk engine for privacy protection and anomaly detection.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Dashboard](#dashboard)
- [Authentication](#authentication)
- [API Documentation](#api-documentation)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

### Real-time Event Processing
- Collect events from Smart TV/OTT platforms (play, pause, seek, errors, etc.)
- High-performance event streaming with async queue-based processing
- Persistence guaranteed through SQLite database

### Advanced Compliance Risk Detection
- **GDPR/CCPA Compliance**: EU user consent status and California region processing
- **Time-window Based Analysis**: Multi-region access and high-frequency activity detection within 1 hour
- **ML-based Anomaly Detection**: Statistical anomaly detection using scikit-learn
- **Subscription Plan Impact**: Risk adjustment based on premium/basic user plans

### Real-time Monitoring
- Interactive dashboard based on Chart.js
- Risk level distribution charts (low/medium/high)
- Real-time metric updates (every 5 seconds)

### Secure Authentication
- JWT-based authentication system
- Role-based access control (admin/analyst)
- Secure password hashing (PBKDF2)

---

## Architecture

```
Smart TV Client ──► [Ingest API] ──► [Queue] ──► [Consumer Service]
                        │               │               │
                        ▼               ▼               ▼
                   [Validation]    [In-Memory]    [Risk Analysis]
                        │               │               │
                        ▼               ▼               ▼
                   [JWT Auth]     [Redis/Kafka     [Compliance Rules]
                                   (Future)]        │
                                                   ▼
                                             [Database]
                                             │
                                             ▼
                                       [Analytics APIs]
                                             │
                                             ▼
                                       [Web Dashboard]
```

### Core Components

- **Ingest API**: FastAPI-based event collection endpoint
- **Queue**: In-memory queue (extensible to Redis/Kafka)
- **Consumer**: Event processing and risk analysis
- **Database**: SQLite-based data persistence
- **Dashboard**: Real-time web interface

---

## Quick Start

### Prerequisites

- Python 3.12+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/deokhwajeong/ott-compliance-events-pipeline.git
cd ott-compliance-events-pipeline

# Create virtual environment (optional)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Generate Test Data

```bash
# Generate fake events (1000 events, 10 concurrent requests)
python src/scripts/generate_fake_events.py --events 1000 --concurrency 10
```

---

## Dashboard

Access the real-time dashboard at `http://localhost:8000` in your web browser.

### Features
- **Real-time Metrics**: Event processing statistics and risk distribution
- **Risk Charts**: Donut charts visualizing risk levels
- **Recent Results**: List of recently processed events
- **Admin Features**: Event processing control after login

---

## Authentication

Admin endpoints require JWT token-based authentication.

### Test Accounts

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| analyst | analyst123 | Analyst |

### Login Method

```bash
# Obtain token
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# Response example
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using Protected Endpoints

```bash
# Request with authorization header
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/compliance/summary
```

---

## API Documentation

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Web dashboard |
| GET | /api | Health check |
| POST | /events | Event collection |
| POST | /token | JWT token issuance |

### Protected Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /process/one | Process single event |
| POST | /process/drain | Process all pending events |
| GET | /stats/summary | Processing statistics summary |
| GET | /results/latest | Latest processing results |
| GET | /compliance/summary | Risk level summary |

### Event Model

```json
{
  "event_id": "evt_123",
  "user_id": "user_42",
  "device_id": "tv_lg_abc123",
  "content_id": "movie_987",
  "event_type": "PLAY",
  "timestamp": "2026-01-02T12:34:56Z",
  "region": "NL",
  "is_eu": true,
  "has_consent": false,
  "ip_address": "203.0.113.10",
  "subscription_plan": "premium",
  "error_code": null,
  "extra_metadata": {
    "app_version": "1.2.3",
    "network_type": "wifi"
  }
}
```

---

## Tech Stack

### Backend
- **Python 3.12+**: Main programming language
- **FastAPI**: High-performance web framework
- **SQLAlchemy**: ORM and database management
- **Pydantic**: Data validation and serialization

### Machine Learning & Analytics
- **scikit-learn**: ML-based anomaly detection
- **NumPy**: Numerical computing
- **Chart.js**: Data visualization

### Security
- **PyJWT**: JWT token handling
- **PassLib**: Password hashing
- **python-multipart**: Form data processing

### Development Tools
- **pytest**: Unit testing
- **Alembic**: Database migrations
- **Uvicorn**: ASGI server

---

## Project Structure

```
ott-compliance-events-pipeline/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI application
│       ├── auth.py              # JWT authentication system
│       ├── models.py            # SQLAlchemy models
│       ├── schemas.py           # Pydantic schemas
│       ├── db.py                # Database connection
│       ├── queue.py             # Queue implementation
│       ├── consumer.py          # Event consumer
│       ├── compliance_rules.py  # Risk analysis rules
│       └── templates/
│           └── dashboard.html   # Web dashboard
├── scripts/
│   └── generate_fake_events.py  # Test data generator
├── tests/
│   └── test_app.py             # Unit tests
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
└── LICENSE                     # MIT License
```

---

## Testing

```bash
# Run all tests
pytest tests/

# Detailed output
pytest tests/ -v

# Run specific test
pytest tests/test_app.py::test_event_schema -v
```

---

## Contributing

Contributions are welcome! Please report issues or submit pull requests.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

**Contact**: If you have any issues or questions, please open an [issue](https://github.com/deokhwajeong/ott-compliance-events-pipeline/issues).

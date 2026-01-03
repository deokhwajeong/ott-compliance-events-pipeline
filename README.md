# ott-compliance-events-pipeline

Smart TV/OTT event ingestion and analytics pipeline with a simple compliance risk engine for privacy and abnormal behavior detection.

---

## 1. Problem

Global OTT and Smart TV platforms receive millions of client-side events every day: play, pause, seek, errors, device info, region, and more.  
Product and operations teams use this telemetry to monitor service health and user experience, while legal/privacy teams need visibility into potential compliance risks (e.g., GDPR/CCPA violations, suspicious access patterns).

This project implements a small-scale backend that:

- Collects Smart TV playback events via an ingest API  
- Streams them through a lightweight queue into a consumer service  
- Aggregates metrics for monitoring (content health, error rates, usage by region)  
- Runs a simple compliance risk engine on top of the events  
- Exposes APIs to query both health stats and compliance risk signals  

---

## 2. High-level Architecture

Smart TV Client (simulated)
|
v
[Ingest API] --- simple auth / validation
|
v
[Queue] --- in-memory or Redis-backed
|
v
[Consumer Service]

store raw events

update aggregates (per content / region / device)

run compliance rules -> risk scores
|
v
[Analytics & Compliance APIs]

/stats/...

/compliance/...

yaml
코드 복사

Core components:

- **Ingest API (FastAPI)**: Receives JSON events from Smart TV clients.  
- **Queue**: Simple abstraction (in-memory to start; could be swapped for Redis/Kafka).  
- **Consumer**: Dequeues events, writes raw logs, updates aggregates, computes compliance risk scores.  
- **Analytics API**: Read-only endpoints for health metrics (e.g., error rates per title/region).  
- **Compliance API**: Read-only endpoints for risk insights (e.g., potential GDPR/CCPA issues).  

---

## 3. Event Model

Example JSON payload (Smart TV → Ingest API):

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
  "error_code": null,
  "extra_metadata": {
    "app_version": "1.2.3",
    "network_type": "wifi"
  }
}
Key fields used for compliance/risk:

is_eu, has_consent: Used to simulate GDPR-related risks.

region: Used to simulate CCPA (e.g., "US-CA" for California).

user_id, device_id, ip_address: Used to detect abnormal access patterns.

error_code: Used to detect potential content/security issues.

4. Compliance Risk Engine (Rule-based)
The first version uses a simple rule-based engine implemented in compliance_rules.py.

Example rules:

GDPR-like privacy risk

EU user (is_eu = true) sends events with has_consent = false

→ raise privacy_risk = HIGH

CCPA-like retention risk

User is marked as do_not_track or requested deletion (simulated flag), but continues sending events

→ retention_risk = HIGH

Account sharing / abnormal access

Same user_id active from more than N distinct regions or IPs within a short time window

→ account_risk = MEDIUM/HIGH

Content or app security/quality

Specific content_id or device_id exhibits error rate above a threshold

→ content_risk = HIGH

Risk scores are stored alongside aggregates and surfaced via the compliance APIs.

5. APIs
5.1 Ingest API (write)
POST /events

Request body: playback event JSON (see model above)

Behavior:

Validate & enqueue event

Return 202 Accepted if queued successfully

5.2 Analytics APIs (read)
GET /stats/summary
Returns overall counts, play time, error rates (global).

GET /stats/content/{content_id}
Returns metrics for a specific title: plays, watch time, error rate, top regions.

GET /stats/region/{region}
Returns metrics for a given region: plays, error distribution, device mix.

5.3 Compliance APIs (read)
GET /compliance/summary
Overall counts of events flagged by each rule (privacy, account, content).

GET /compliance/events
List of high-risk events with pagination.

GET /compliance/regions
Aggregated risk by region (e.g., EU vs non-EU, CA vs non-CA).

6. Tech Stack
Language: Python 3.x

Web framework: FastAPI

Data store: SQLite or PostgreSQL (configurable)

Queue: In-memory queue to start (could be replaced by Redis/Kafka)

Testing: pytest

7. Getting Started
bash
코드 복사
# 1. Clone
git clone https://github.com/deokhwajeong/ott-compliance-events-pipeline.git
cd ott-compliance-events-pipeline

# 2. (Optional) Create virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the API (dev mode)
uvicorn src.app.main:app --reload
The API will be available at http://localhost:8000.

8. Generating Fake Smart TV Events
A simple script at src/scripts/generate_fake_events.py can simulate Smart TV clients by POSTing random events to /events.

The script generates:

Normal viewing behavior (PLAY/STOP/SEEK)

EU users with/without consent (to trigger privacy risk)

Users with abnormal multi-region access (to trigger account risk)

Titles or devices with high error rates (to trigger content risk)

Example usage:

bash
코드 복사
python src/scripts/generate_fake_events.py --events 1000 --concurrency 10
9. Repository Structure
text
코드 복사
.
├── README.md
├── requirements.txt
├── src/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entrypoint (Ingest + Analytics + Compliance APIs)
│   │   ├── models.py            # ORM models (raw events, aggregates, risk tables)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── db.py                # DB connection (SQLite/Postgres)
│   │   ├── queue.py             # Simple queue abstraction (in-memory / Redis)
│   │   ├── consumer.py          # Event consumption, aggregation, risk scoring
│   │   └── compliance_rules.py  # Rule-based compliance/risk engine
│   └── scripts/
│       └── generate_fake_events.py   # Smart TV event simulator
└── tests/
    ├── __init__.py
    └── test_api_basic.py
10. Future Work
Replace in-memory queue with Kafka or Redis Streams

Add richer risk models (e.g., anomaly detection over time windows)

Integrate a simple dashboard (Grafana or custom frontend) on top of the APIs

Extend the schema to cover subscription/plan info and link to revenue impact

Add a small recommendation service using viewing logs (collaborative filtering or GNN-based models)

Add authentication/authorization for admin endpoints

11. Why this project?
This project is inspired by real-world OTT and Smart TV platforms that must:

Operate at scale across regions and devices

Monitor service health from client telemetry

Respect evolving privacy regulations (GDPR/CCPA)

Detect abnormal behavior and mitigate risk early

It is designed as a small, self-contained system to demonstrate:

End-to-end backend design (ingest → queue → consumer → APIs)

Experience with distributed system patterns on a smaller scale

Awareness of data privacy and compliance risks in streaming platforms

Ability to turn Smart TV/OTT domain experience into concrete system design and code

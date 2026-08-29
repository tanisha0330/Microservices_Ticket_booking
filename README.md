# TicketFlow

A production-ready **microservices-based event booking platform** built with FastAPI, PostgreSQL, Redis, and async Python (3.12).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Environment Variables](#environment-variables)
- [Running the Services](#running-the-services)
- [API Overview](#api-overview)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Phase 2: Event Backbone](#phase-2-event-backbone)

---

## Project Overview

TicketFlow allows users to browse events, book tickets, and process payments — all through an API-gateway-fronted set of independent microservices. Each service owns its own database schema, manages its own migrations with Alembic, and communicates with peers over HTTP.

**Key features:**
- JWT-based authentication with access + refresh tokens
- Seat locking via Redis (TTL-based, prevents double-booking)
- Async throughout: SQLAlchemy 2.0 async, asyncpg, redis[asyncio]
- Structured JSON logging with structlog
- Pydantic v2 request/response validation
- Consistent error envelope: `{"error": {"code": "...", "message": "...", "details": {}, "correlation_id": "..."}}`

---

## Architecture

```
Client
  |
  v
API Gateway  (port 8000)   <- single entry point, JWT validation, request routing
  |
  +---> User Service    (port 8001)   <- auth, registration, profiles
  |
  +---> Catalog Service (port 8002)   <- events, venues, seat maps
  |
  +---> Booking Service (port 8003)   <- reservations, seat locks (Redis)
  |
  +---> Payment Service (port 8004)   <- payment processing, webhooks

Shared Infrastructure:
  - PostgreSQL (port 5433)  <- each service has its own database
  - Redis      (port 6379)  <- seat locks, token blacklist, caching
```

### Service Responsibilities

| Service         | Database            | Core Domain                                 |
|----------------|---------------------|---------------------------------------------|
| User Service   | `ticketflow_users`  | Registration, login, JWT tokens, profiles   |
| Catalog Service| `ticketflow_catalog`| Events, venues, categories, seat inventory  |
| Booking Service| `ticketflow_booking`| Bookings, seat selection, Redis seat locks  |
| Payment Service| `ticketflow_payment`| Payment intents, refunds, webhook handling  |
| API Gateway    | -                   | Routing, JWT auth, rate limiting, CORS      |

---

## Prerequisites

| Tool       | Version  | Notes                                      |
|-----------|----------|--------------------------------------------|
| Python    | 3.12+    | `python --version`                         |
| PostgreSQL| 15+      | Running on port **5433**                   |
| Redis     | 7+       | Running on port **6379**                   |
| pip       | latest   | `pip install --upgrade pip`                |

### Python packages (install once, globally or in a venv):

```powershell
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic `
            pyjwt bcrypt redis python-dotenv structlog pydantic-settings `
            httpx pytest pytest-asyncio fakeredis
```

---

## Setup Instructions

### 1. Clone and navigate

```powershell
cd X:\ticket-booking\ticketflow
```

### 2. Configure environment

```powershell
Copy-Item .env.example .env
# Edit .env with your actual values (especially JWT_SECRET_KEY)
```

### 3. Create databases

Connect to PostgreSQL and create one database per service:

```sql
CREATE DATABASE ticketflow_users;
CREATE DATABASE ticketflow_catalog;
CREATE DATABASE ticketflow_booking;
CREATE DATABASE ticketflow_payment;
```

Or run via psql:

```powershell
psql -h localhost -p 5433 -U ticketflow -c "CREATE DATABASE ticketflow_users;"
psql -h localhost -p 5433 -U ticketflow -c "CREATE DATABASE ticketflow_catalog;"
psql -h localhost -p 5433 -U ticketflow -c "CREATE DATABASE ticketflow_booking;"
psql -h localhost -p 5433 -U ticketflow -c "CREATE DATABASE ticketflow_payment;"
```

### 4. Run Alembic migrations (per service)

```powershell
cd X:\ticket-booking\ticketflow\services\user-service
alembic upgrade head

cd X:\ticket-booking\ticketflow\services\catalog-service
alembic upgrade head

cd X:\ticket-booking\ticketflow\services\booking-service
alembic upgrade head

cd X:\ticket-booking\ticketflow\services\payment-service
alembic upgrade head
```

### 5. Start all services

```powershell
cd X:\ticket-booking\ticketflow
.\start_all.ps1
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable                          | Default / Example                                   | Description                                      |
|----------------------------------|-----------------------------------------------------|--------------------------------------------------|
| `POSTGRES_HOST`                  | `localhost`                                         | PostgreSQL host                                  |
| `POSTGRES_PORT`                  | `5433`                                              | PostgreSQL port                                  |
| `POSTGRES_USER`                  | `ticketflow`                                        | PostgreSQL username                              |
| `POSTGRES_PASSWORD`              | `ticketflow123`                                     | PostgreSQL password                              |
| `REDIS_URL`                      | `redis://localhost:6379`                            | Redis connection URL                             |
| `JWT_SECRET_KEY`                 | *(change this!)*                                    | Secret used to sign JWTs — min 32 chars          |
| `JWT_ALGORITHM`                  | `HS256`                                             | JWT signing algorithm                            |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`| `15`                                                | Access token lifetime in minutes                 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`  | `7`                                                 | Refresh token lifetime in days                   |
| `USER_SERVICE_URL`               | `http://localhost:8001`                             | Internal URL for user service                    |
| `CATALOG_SERVICE_URL`            | `http://localhost:8002`                             | Internal URL for catalog service                 |
| `BOOKING_SERVICE_URL`            | `http://localhost:8003`                             | Internal URL for booking service                 |
| `PAYMENT_SERVICE_URL`            | `http://localhost:8004`                             | Internal URL for payment service                 |
| `PAYMENT_WEBHOOK_SECRET`         | *(change this!)*                                    | Secret for verifying payment webhooks            |
| `SEAT_LOCK_TTL_SECONDS`          | `300`                                               | Seconds a seat is held in Redis before releasing |
| `MAX_SEATS_PER_BOOKING`          | `10`                                                | Maximum seats allowed per booking                |

> **Security note:** Always rotate `JWT_SECRET_KEY` and `PAYMENT_WEBHOOK_SECRET` before deploying to production.

---

## Running the Services

### All at once (recommended)

```powershell
.\start_all.ps1    # starts Redis + all 5 services in separate terminals
.\stop_all.ps1     # kills all uvicorn processes
```

### Individually

```powershell
# Set PYTHONPATH so shared modules resolve correctly
$env:PYTHONPATH = "X:\ticket-booking\ticketflow"

# User Service
cd X:\ticket-booking\ticketflow\services\user-service
uvicorn app.main:app --port 8001 --reload

# Catalog Service
cd X:\ticket-booking\ticketflow\services\catalog-service
uvicorn app.main:app --port 8002 --reload

# Booking Service
cd X:\ticket-booking\ticketflow\services\booking-service
uvicorn app.main:app --port 8003 --reload

# Payment Service
cd X:\ticket-booking\ticketflow\services\payment-service
uvicorn app.main:app --port 8004 --reload

# API Gateway
cd X:\ticket-booking\ticketflow\services\gateway
uvicorn app.main:app --port 8000 --reload
```

---

## API Overview

All endpoints are accessible through the **API Gateway at `http://localhost:8000`**.

> Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### User Service (`/users`)

| Method | Path                        | Auth     | Description                        |
|--------|-----------------------------|----------|------------------------------------|
| POST   | `/users/register`           | None     | Register a new user                |
| POST   | `/users/login`              | None     | Login, returns access+refresh JWT  |
| POST   | `/users/refresh`            | Refresh  | Obtain a new access token          |
| POST   | `/users/logout`             | Bearer   | Revoke refresh token               |
| GET    | `/users/me`                 | Bearer   | Get current user profile           |
| PATCH  | `/users/me`                 | Bearer   | Update current user profile        |

### Catalog Service (`/catalog`)

| Method | Path                        | Auth     | Description                        |
|--------|-----------------------------|----------|------------------------------------|
| GET    | `/catalog/events`           | None     | List/search events                 |
| GET    | `/catalog/events/{id}`      | None     | Get event details                  |
| POST   | `/catalog/events`           | Admin    | Create an event                    |
| PATCH  | `/catalog/events/{id}`      | Admin    | Update an event                    |
| DELETE | `/catalog/events/{id}`      | Admin    | Delete an event                    |
| GET    | `/catalog/venues`           | None     | List venues                        |
| GET    | `/catalog/venues/{id}`      | None     | Get venue + seat map               |

### Booking Service (`/bookings`)

| Method | Path                        | Auth     | Description                         |
|--------|-----------------------------|----------|-------------------------------------|
| POST   | `/bookings`                 | Bearer   | Create booking + lock seats (Redis) |
| GET    | `/bookings`                 | Bearer   | List user's bookings                |
| GET    | `/bookings/{id}`            | Bearer   | Get booking details                 |
| DELETE | `/bookings/{id}`            | Bearer   | Cancel booking, release seats       |
| POST   | `/bookings/{id}/confirm`    | Bearer   | Confirm booking after payment       |

### Payment Service (`/payments`)

| Method | Path                        | Auth     | Description                         |
|--------|-----------------------------|----------|-------------------------------------|
| POST   | `/payments/initiate`        | Bearer   | Create a payment intent             |
| GET    | `/payments/{id}`            | Bearer   | Get payment status                  |
| POST   | `/payments/webhook`         | HMAC     | Handle payment provider webhooks    |
| POST   | `/payments/{id}/refund`     | Bearer   | Request a refund                    |

---

## Running Tests

Each service has its own test suite under `tests/`.

```powershell
# Run tests for a specific service
cd X:\ticket-booking\ticketflow\services\user-service
pytest tests/ -v

# Run all tests across all services
cd X:\ticket-booking\ticketflow
pytest services/ -v --tb=short

# Run with coverage
pytest services/ --cov=app --cov-report=term-missing
```

**Test stack:**
- `pytest` + `pytest-asyncio` for async test support
- `fakeredis` for in-memory Redis (no real Redis needed in tests)
- `httpx.AsyncClient` with FastAPI's `ASGITransport` for endpoint testing
- In-memory SQLite or test PostgreSQL DB for database tests

---

## Project Structure

```
ticketflow/
├── .env                          # Local environment variables (gitignored)
├── .env.example                  # Template for environment variables
├── README.md                     # This file
├── start_all.ps1                 # Start all services + Redis
├── stop_all.ps1                  # Stop all uvicorn processes
│
└── services/
    ├── gateway/                  # API Gateway (port 8000)
    │   ├── app/
    │   │   ├── main.py
    │   │   ├── config.py
    │   │   ├── middleware/
    │   │   └── routers/
    │   └── tests/
    │
    ├── user-service/             # User Service (port 8001)
    │   ├── app/
    │   │   ├── main.py
    │   │   ├── config.py
    │   │   ├── models.py
    │   │   ├── schemas.py
    │   │   ├── database.py
    │   │   ├── dependencies.py
    │   │   └── routers/
    │   ├── alembic/
    │   ├── alembic.ini
    │   └── tests/
    │
    ├── catalog-service/          # Catalog Service (port 8002)
    │   ├── app/
    │   ├── alembic/
    │   └── tests/
    │
    ├── booking-service/          # Booking Service (port 8003)
    │   ├── app/
    │   ├── alembic/
    │   └── tests/
    │
    └── payment-service/          # Payment Service (port 8004)
        ├── app/
        ├── alembic/
        └── tests/
```

---

## Phase 2: Event Backbone

Booking-service writes events (`SEATS_LOCKED`, `BOOKING_CONFIRMED`, `BOOKING_FAILED`, `BOOKING_CANCELLED`, `BOOKING_EXPIRED`) to an outbox table and an in-process relay publishes them to **Redpanda** (Kafka-wire-compatible) on the `booking.events` topic. Two new consumer services fan out from there:

| Service | Reads | Does | Port |
|---|---|---|---|
| `notification-service` | `booking.events` | logs a stub notification per `BOOKING_CONFIRMED`/`FAILED`/`CANCELLED` | 8005 |
| `analytics-service` | `booking.events` | increments per-event-type counters, exposes `GET /stats` | 8006 |

Both consumers are idempotent (a `processed_events` table keyed by the event's own id) and retry a failing handler 3x before routing the message to `booking.events.dlq` rather than blocking the partition. Each also auto-reconnects if the broker drops out from under it, replaying any backlog once it's back.

### Running it

```bash
docker-compose up -d --build
```

This starts Redpanda, Redpanda Console, a shared Postgres (`ticketflow_notification` / `ticketflow_analytics` databases), and both new services — containerized independently of the 5 Phase 1 services, which keep running via `start_all.ps1` against `localhost`.

- Redpanda Console (topics, messages, consumer lag): http://localhost:8080
- `curl localhost:8006/stats` — live event counts
- `curl localhost:8005/health`, `curl localhost:8006/health`

### Chaos scripts

`scripts/chaos_kill_broker.ps1` and `scripts/chaos_kill_consumer.ps1` stop/start the Redpanda broker and `notification-service` respectively — verified against the live stack that no event is lost or double-processed either way (uncommitted offsets replay after restart, `processed_events` prevents double-counting).

---

## Phase 3: AI Agent System

Six new microservices add an agentic layer on top of Phase 1/2: a single chat entry point that classifies intent, routes to a sub-agent, and runs every message through input/output guardrails before it's seen or returned. No real LLM is used anywhere (no API keys) — every "AI" step (intent classification, constraint extraction, itinerary generation, prompt-injection/PII detection, hallucination checking) is deterministic regex/heuristic Python, documented as such in each service's code.

| Service | Does | Port |
|---|---|---|
| `agent-gateway` | Chat entry point: guardrail → intent classify → route → guardrail → trace → persist | 8007 |
| `travel-planner-agent` | Multi-turn constraint gathering (dates/budget/interests) → itinerary, backed by RAG | 8008 |
| `support-agent` | Booking inquiry / refund, calls booking-service and payment-service on the user's behalf via a forwarded JWT | 8009 |
| `rag-service` | Vector search over destination/policy content (pgvector, deterministic mock embeddings — not semantically meaningful, just a consistent stand-in) | 8010 |
| `guardrail-service` | Prompt-injection + PII detection/redaction, hallucination heuristic | 8011 |
| `eval-service` | Records one trace per gateway conversation turn (`agent_traces`) | 8012 |

Scoped down from the literal `phase3_prompt.md` spec in a few places (each flagged in the relevant service's own README): fewer tables where RAG/the shared Postgres already cover the same data, Guardrail Service reduced from 3 tables/5 endpoints to 1 table/3 endpoints, Eval Service called once per gateway turn rather than once per sub-agent.

The refund amount is always computed by `support-agent`'s own `RefundRulesEngine` (>7 days out = 100%, within 7 days = 50%, within 24h = 0%, event cancelled = 100%) — the user-stated amount is never trusted.

### Running it

```powershell
docker compose up -d postgres rag-postgres redis
.\start_phase3.ps1
```

The 6 services run as bare `uvicorn --reload` processes (like Phase 1), not containerized, since they need to reach the host-run Phase 1 services on `localhost`. Entry point: `http://localhost:8007/docs`.

### Real issues found and fixed while building this

- **Guardrail thresholds under-scored 3 of the spec's 12 literal red-team strings** (`"you are now"`, `"pretend to be/don't have"`, `"execute this command"` each scored just under the 0.7 block threshold). Found by actually running the red-team suite from `phase3_prompt.md` against the live gateway, not just unit tests — all 12/12 now block correctly end-to-end.
- **Intent classifier had no conversation memory.** Once `travel-planner-agent` asks a constraint-gathering follow-up ("what dates?"), a free-text reply that doesn't contain a travel keyword (e.g. "I love art museums and good food") fell through to `GENERAL_QA` and derailed the flagship multi-turn demo. Fixed with a narrow sticky-route: a weak `GENERAL_QA`/`CHITCHAT` classification continues an already-active `TRAVEL_PLANNING` conversation instead of resetting it; an explicit refund/booking/escalation ask still overrides, since those are matched before this check runs. `ponytail:` comment in `agent-gateway/app/orchestrator.py` names the heuristic's ceiling.
- **No Redis container existed anywhere in the project**, despite both `booking-service` (seat locks, refresh-token revocation) and `agent-gateway` (rate limiting) depending on `redis://localhost:6379` by default. Added to `docker-compose.yml`.
- **A native Windows PostgreSQL service already listening on port 5433** was silently shadowing the Docker `postgres` container for every new `localhost` connection (the databases existed fine inside the container — new connections were just being routed to the wrong server entirely). Remapped the container to host port 5440 rather than touch the unrelated system service; `start_phase3.ps1` overrides `POSTGRES_PORT=5440` for just these 6 services, leaving Phase 1/2 defaults untouched.

### NEEDS HUMAN REVIEW

- **Process stability on this machine**: bare `uvicorn --reload` windows for the Phase 3 services (and some Phase 1 ones) have been observed exiting on their own after tens of seconds to a few minutes, with no error logged — not a code exception, just the process disappearing. Root cause not identified (suspected: this dev sandbox's process/session lifecycle, not the application code — a `--reload`-less foreground run of the same service stayed up without issue during debugging). Worth running via `docker compose` or a real process manager if this recurs outside this environment.
- **Full refund/booking-inquiry end-to-end test (support-agent → booking-service → payment-service) was not completed** — Phase 1's `user-service`, `catalog-service`, and `payment-service` processes died shortly after `start_all.ps1` launched them (same instability as above), so no real booking existed to test a refund against. The travel-planning multi-turn flow above was verified live end-to-end and does not depend on Phase 1.
- A separate native (WSL-hosted) Redis is also reachable on `localhost:6379` alongside the new Docker container, via the same "more specific loopback binding wins" mechanism as the Postgres issue above. Functionally harmless here (rate-limit/seat-lock keys are simple namespaced counters, so either backend works identically) but worth knowing about if debugging "missing" rate-limit or seat-lock state.

---

## Notes

- **PYTHONPATH** must be set to `X:\ticket-booking\ticketflow` so that inter-service shared imports resolve correctly. `start_all.ps1` handles this automatically.
- Each service reads its own `.env` (or the root `.env`) via `pydantic-settings`.
- Seat locks in Redis use the key pattern `seat_lock:{event_id}:{seat_id}` with a configurable TTL (`SEAT_LOCK_TTL_SECONDS`).
- JWTs use short-lived access tokens (15 min) and longer-lived refresh tokens (7 days). Refresh tokens are tracked in Redis for revocation.

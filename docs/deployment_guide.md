# Production Deployment Guide

This document outlines the steps required to deploy the Ben El Fareed Backend securely and robustly in a production environment.

## 1. Required Environment Variables

Ensure the following environment variables are set securely in your production environment (e.g., via AWS Secrets Manager, GitHub Secrets, or a secure `.env` file not checked into version control). **Do not use `.env.example` directly in production.**

- `ENVIRONMENT`: Must be set to `production`.
- `LOG_LEVEL`: Recommended `INFO` or `WARNING`.
- `ENABLE_HSTS`: Set to `True` to enforce HTTP Strict Transport Security.
- `ALLOWED_ORIGINS`: JSON array of frontend origins allowed to access the API (e.g., `["https://www.yourdomain.com", "https://admin.yourdomain.com"]`).

**Supabase Configuration:**

- `SUPABASE_URL`: Your Supabase project URL.
- `SUPABASE_ANON_KEY`: Your Supabase public anonymous key.
- `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key (Backend only, **never** expose this to the frontend).

**Database Configuration:**

- `DATABASE_URL`: Connection string (start with `postgresql://`). Use the IPv4 connection pooler provided by Supabase if deploying on serverless.
- `DB_POOL_SIZE`: Adjust based on deployment scale (default 5).
- `DB_MAX_OVERFLOW`: Adjust based on deployment scale (default 10).
- `DB_POOL_TIMEOUT`: Connection timeout in seconds (default 30).

## 2. Supabase Setup Requirements

1. **PostgreSQL Database:** Ensure Supabase PostgreSQL is running.
2. **Storage:** Ensure a storage bucket named `products` exists for product images. The backend manages this via the Service Role Key.
3. **Auth:** Configure Supabase Auth settings to match the domains used by the frontend applications.

## 3. Database Migration Commands

Before starting the application server, you must run the database migrations against the production database.

Run this command from the root of the project:

```bash
alembic upgrade head
```

This applies all unapplied migrations safely.

## 4. Docker Build Command

To build the production Docker image, run the following command from the root of the project:

```bash
docker build -t elfareed-backend:latest .
```

This builds a Python 3.14-slim image running under a non-root `appuser`.

## 5. Docker Run/Deployment Configuration

Run the container using the appropriate environment variables. Assuming your variables are in a securely managed `.env` file (which is excluded from the build via `.dockerignore`):

```bash
docker run -d \
  --name elfareed-backend \
  -p 8000:8000 \
  --env-file .env \
  elfareed-backend:latest
```

_Note: In production environments like AWS ECS, Kubernetes, or Google Cloud Run, environment variables are typically injected by the orchestrator._

## 6. Health-check Endpoints

- **Liveness Check (`GET /api/v1/health`):** Verifies the API process is alive.
- **Readiness Check (`GET /api/v1/health/ready`):** Verifies the database connectivity by executing a simple `SELECT 1` query. Returns a 503 status code if the database is unreachable, without leaking any connection credentials.

## 7. CORS Configuration

Wildcard CORS (`*`) is disabled. You must explicitly configure `ALLOWED_ORIGINS` to contain the URLs of your frontends. Example:

```json
["https://store.benelfareed.com", "https://admin.benelfareed.com"]
```

## 8. HTTPS Requirements

The API assumes HTTPS is terminated at the load balancer or reverse proxy (e.g., Nginx, AWS ALB, Cloudflare).
Set `ENABLE_HSTS=True` in your environment to ensure the backend instructs browsers to strictly use HTTPS for all future requests.

## 9. Logging Expectations

Logging is handled via standard output (stdout), which is captured seamlessly by Docker, Kubernetes, and CloudWatch.
The default format includes timestamps, log level, and the logger name.
Sensitive information (like Supabase Service Role keys, JWT tokens, and database passwords) are strictly excluded from logs. Stack traces are sanitized before reaching clients.

## 10. Rollback Procedure

If a deployment fails:

1. **Revert the Docker Image:** Deploy the previous known-good Docker image tag.
2. **Revert Migrations (if applicable):** If the failure was due to a destructive database schema change, run `alembic downgrade <revision_id>` using the previous deployment's codebase before reverting the image. _Note: Forward-only migrations are highly recommended to avoid needing downgrades._

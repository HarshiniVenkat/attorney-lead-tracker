# Alma — Lead Management

A public lead-capture form and an internal, auth-guarded dashboard for managing
the leads it produces.

- **Public** — a prospect submits their name, email and resume. No account needed.
- **Emails** — on submission, a confirmation goes to the prospect and a notification to an attorney.
- **Internal** — attorneys sign in, browse and search leads, download resumes, and move a lead from `PENDING` to `REACHED_OUT`.

**Stack:** Next.js 15 (App Router) · FastAPI · PostgreSQL · MinIO (S3) · MailHog (SMTP)

---

## Quick start

Requires Docker.

```bash
make up     # build and start everything
make seed   # create the attorney login
```

| Surface | URL | Credentials |
|---|---|---|
| Public form | http://localhost:3000/apply | — |
| Internal dashboard | http://localhost:3000/admin/leads | `attorney@example.com` / `changeme123` |
| API docs (Swagger) | http://localhost:8000/docs | — |
| MailHog inbox | http://localhost:8025 | — |
| MinIO console | http://localhost:9001 | `minioadmin` / `minioadmin` |

Submit the form at `/apply`, then open **MailHog** to read both emails and
**`/admin/leads`** to work the lead.

`make help` lists every target.

> **Port note:** Postgres is published on host port **5433**, not 5432, because
> 5432 is commonly already taken. Change `POSTGRES_HOST_PORT` in `.env` if
> needed — it does not affect container-to-container traffic.

---

## Layout

```
backend/                          FastAPI service
  app/
    api/v1/routes/                HTTP layer only
    services/                     business rules (state machine, email orchestration)
    repositories/                 all database queries
    models/                       SQLAlchemy ORM
    schemas/                      Pydantic request/response contracts
    integrations/
      storage/                    StorageBackend port: s3 | local
      email/                      EmailBackend port: smtp | console
    validators/upload.py          magic-byte resume validation
    templates/email/              Jinja2 HTML + text emails
    core/                         config, security, logging, errors, rate limiting
  alembic/versions/               migrations
  tests/                          68 tests against real Postgres

frontend/                         Next.js app
  src/
    app/apply/                    public form
    app/admin/                    auth-guarded dashboard
    app/api/                      route handlers (cookie exchange, resume proxy)
    components/ui/                Button, Field, Badge, Alert primitives
    lib/                          typed API client, session, formatting
    middleware.ts                 /admin route guard

SYSTEM_OVERVIEW.md                how it works and why — start here
```

Layering is strict and one-directional:
`routes → services → repositories → models`. Routes never touch the database;
repositories never contain business rules.

---

## Common tasks

```bash
make test         # backend test suite
make lint         # ruff + eslint
make logs         # tail all services
make psql         # open a database shell
make migrate      # apply migrations
make clean        # tear down and delete all data
```

Frontend checks:

```bash
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run build
```

Managing attorney accounts:

```bash
docker compose exec backend python -m app.cli create-user --email a@b.com --name "A B"
docker compose exec backend python -m app.cli deactivate-user --email a@b.com
```

Deactivating preserves the account's audit trail; deleting it would not. See
[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md#attorneys-are-deactivated-never-deleted).

---

## Configuration

Everything is environment-driven. `make up` copies `.env.example` to `.env` on
first run; the defaults work out of the box.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `JWT_SECRET` | Token signing key — **replace before deploying** |
| `STORAGE_BACKEND` | `s3` (MinIO/AWS) or `local` (disk) |
| `EMAIL_BACKEND` | `smtp` (MailHog/any relay) or `console` (logs only) |
| `ATTORNEY_NOTIFICATION_EMAIL` | Who receives new-lead notifications |
| `MAX_RESUME_SIZE_BYTES` | Upload cap, default 5 MB |
| `SEED_ADMIN_*` | Account created by `make seed` |

Swapping to a real provider is a config change, not a code change: point
`SMTP_HOST` at SendGrid/SES, or set `STORAGE_BACKEND=s3` with real AWS
credentials.

---

## Notes on the implementation

New to the project? [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) is a plain-language
tour of how everything fits together and why.

A few decisions that aren't obvious from the code alone — all covered there in
more depth:

**Resume uploads are validated by their bytes, not their name.** The `accept`
attribute and the declared `Content-Type` are both client-controlled, so the
authoritative check sniffs magic bytes: `%PDF-` for PDF, and for DOCX a zip
whose central directory actually contains `word/`. An executable renamed to
`.pdf` is rejected with a 415.

**Emails use a transactional outbox.** Both messages are written as rows in the
same database transaction as the lead itself, so a lead can never exist without
a durable record of the emails owed on it. Delivery is attempted afterwards,
off the request path — a mail outage cannot lose a notification or show the
prospect an error. Delivery status is visible per-lead in the dashboard.

**The state machine lives in one table.** `ALLOWED_TRANSITIONS` in
`services/state_machine.py` is the single source of truth; illegal moves return
409. `REACHED_OUT → PENDING` is deliberately absent.

**Auth is httpOnly-cookie based.** FastAPI issues the JWT; a Next.js route
handler puts it in an httpOnly cookie so no script can read it. `middleware.ts`
guards `/admin` for UX, but real enforcement is FastAPI re-validating the token
*and re-checking the account* on every request — so deactivating an attorney
takes effect immediately rather than at token expiry.

### Known limitations

- **Email retry is not implemented.** A failed delivery is recorded as `FAILED` and surfaced in the UI, but nothing retries it. The schema (`attempts`, `next_attempt_at`) already supports it, so the worker is a pure addition.
- **Rate limiting is in-process.** Correct for one instance; a multi-replica deployment needs Redis or edge limiting.
- **Logout is client-side.** JWTs are stateless, so the token stays valid until it expires. Immediate revocation needs a blocklist or short-lived tokens plus refresh.

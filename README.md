# BetweenUs 💗

BetweenUs is a private, two-person mood-sharing space for staying close without starting a conversation. It is a Django + Channels MVP with a warm, mobile-first interface inspired by the supplied BetweenUs mark.

## What is included

- Registration, login, logout, hashed passwords, CSRF protection, and protected private pages.
- One active couple connection per user with expiring, difficult-to-guess invitation codes.
- Eight one-tap moods, active mood expiration, duplicate-click protection, and private history.
- Reactions, in-app notifications, notification preferences, and Do Not Disturb.
- Authenticated WebSocket events for mood and reaction delivery, with the HTTP API as a graceful fallback when a socket is unavailable.
- Responsive landing page, dashboard, moments timeline, notifications, settings, and admin registrations.
- Automated tests for registration, invitation validation and expiration, mood/reaction privacy, invalid input, and anonymous WebSocket rejection.

## Prerequisites

- Python 3.11 or newer.
- PowerShell on Windows, or a standard shell on Linux/macOS.
- Optional for production real-time delivery: Redis.

## Windows PowerShell setup

```powershell
cd betweenus
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py manage.py migrate
py manage.py createsuperuser
py manage.py runserver
```

Open <http://127.0.0.1:8000/>.

If PowerShell blocks activation for the current session, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

On Linux/macOS, use `python3 -m venv .venv`, `source .venv/bin/activate`, and replace `py` with `python`.

## Environment variables

Copy `.env.example` to `.env` and set a unique `DJANGO_SECRET_KEY` before deploying. `DJANGO_DEBUG` defaults to `True` for local work. `DJANGO_ALLOWED_HOSTS` accepts a comma-separated list.

SQLite is used by default. Set `DATABASE_URL` to a PostgreSQL URL in production; `dj-database-url` is included for that configuration. Set `REDIS_URL` to switch Channels from the local in-memory layer to Redis.

## Testing with two accounts

1. Register account A and create an invitation from `/connect/`.
2. Open a private/incognito window, register account B, and paste the invitation code.
3. Both accounts now share the same dashboard. Use two browser windows to see mood events arrive over the WebSocket.
4. Switch off the socket or use a network that blocks WebSockets to verify the mood buttons still save through the HTTP endpoint.
5. Review `/moments/`, `/notifications/`, and `/settings/` from either account.

Run the suite with:

```powershell
py manage.py test
```

Run system checks with:

```powershell
py manage.py check
```

## WebSocket architecture

The ASGI application wraps the WebSocket route in `AuthMiddlewareStack`. The consumer resolves the actual authenticated user and looks up their connected `CoupleConnection`; it never trusts a partner ID sent by the browser. Authorized users join a server-generated `couple_<connection_id>` group. Mood and reaction writes happen through the ORM first, then broadcast a small event to that group. The browser also keeps an HTTP endpoint available as a fallback.

The development configuration uses `InMemoryChannelLayer`, which is appropriate for one local process only. Production deployments with multiple workers should configure Redis with `REDIS_URL`, run behind HTTPS, set `DJANGO_DEBUG=False`, configure a real secret and allowed hosts, collect static files, and serve the ASGI application with Daphne or another ASGI server.

## Publish globally with Render

The repository includes `render.yaml` and `build.sh` for a Render deployment. Render's Django guide supports deploying a web service backed by managed PostgreSQL, and Render web services accept public WebSocket connections. See the step-by-step deployment notes in the project handoff or use this flow:

1. Create a GitHub repository and upload the contents of this `betweenus` folder. The repository root should contain `manage.py`.
2. In Render, choose **New → Blueprint**, connect the GitHub repository, and select `render.yaml`.
3. Set `DJANGO_ALLOWED_HOSTS` to the Render hostname, for example `betweenus.onrender.com`.
4. Set `DJANGO_CSRF_TRUSTED_ORIGINS` to the HTTPS origin, for example `https://betweenus.onrender.com`.
5. Create a Render Key Value/Redis-compatible instance and copy its connection URL into `REDIS_URL` so WebSocket events work across workers.
6. Deploy. The build script collects static files and runs migrations; the start command runs Daphne for HTTP and WebSockets.
7. Open the Render Shell once and run `python manage.py createsuperuser` if you want admin access.

For a custom domain, add it to `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. Keep `DJANGO_DEBUG=False` and never commit `.env` or real secrets.

## Privacy and retention notes

All mood, reaction, notification, and moments queries are scoped to an active connection. Expired moods disappear from the “Today” active-mood cards but remain in the private timeline. Disconnecting closes the active connection and prevents access to the shared history through ordinary application routes; data remains in the database for future retention-policy tooling rather than being silently destroyed.

## Project layout

```text
config/          Django settings, URL routing, WSGI/ASGI entry points
couples/         Models, forms, views, services, consumer, tests, migrations
templates/       Landing, auth, app pages, and reusable navigation
static/css/      Design system and responsive styling
static/js/       Mood, reaction, clipboard, and WebSocket interactions
static/images/   Supplied BetweenUs logo reference
```


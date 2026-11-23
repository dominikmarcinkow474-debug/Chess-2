# CART3R Chess Companion API

A runnable FastAPI service for gaming companion features and chess move analysis. It stores accounts and games in PostgreSQL, authenticates requests with JWT access tokens, validates legal chess moves, and uses Stockfish to recommend the opponent's strongest reply and then your recommended follow-up.

> Engine recommendations are best moves found at the configured search depth/time, not a guarantee of objectively perfect play. Do not use this tool to automate moves in a game or violate a game's rules/terms.

## Architecture

```text
Client (browser / mobile)
        |
        | HTTPS + Bearer JWT
        v
FastAPI routes ─── Auth/JWT + password hashing
        |                     |
        v                     v
SQLAlchemy ORM             PostgreSQL
        |
        +── python-chess: FEN, legal move validation, SAN/PGN
        |
        +── Stockfish UCI engine: best reply + suggested follow-up
```

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| GET | `/health` | No | Health check |
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | Obtain JWT (OAuth2 password form) |
| GET | `/users/me` | Yes | Current user |
| POST | `/games` | Yes | Create game; optional FEN |
| GET | `/games` | Yes | List your games |
| GET | `/games/{id}` | Yes | Get one of your games |
| DELETE | `/games/{id}` | Yes | Delete your game |
| POST | `/games/{id}/moves` | Yes | Play a legal move and analyse response |

Interactive OpenAPI docs: `http://localhost:8000/docs`.

### Move analysis flow

Send `{"uci":"e2e4"}` to `/games/{id}/moves`. UCI examples include `e2e4`, `g1f3`, and promotions such as `e7e8q`. The API:
1. Checks that the game belongs to the authenticated user.
2. Validates the move against the current legal moves.
3. Persists the move and resulting FEN.
4. Uses Stockfish to select the opponent's best reply at the requested depth.
5. Analyses the position after that reply and suggests your next move.

The response includes both UCI and SAN notation, the predicted FEN after the opponent reply, an evaluation, search depth, and terminal-game status. The game FEN stored in the database reflects the move you actually submitted; it does not silently apply the engine's predicted opponent move. You submit the opponent's actual reply as the next move when it occurs.

## Run with Docker (recommended)

Requires Docker Desktop / Docker Engine and Docker Compose.

1. Copy `.env.example` to `.env`.
2. Set a long random `JWT_SECRET_KEY` and a strong `POSTGRES_PASSWORD`.
3. Start the stack:

   ```bash
   docker compose up --build
   ```

4. Open `http://localhost:8000/docs`.
5. Stop with `Ctrl+C`, then `docker compose down`. Use `docker compose down -v` only if you intentionally want to delete the database volume.

The compose stack includes PostgreSQL and installs Stockfish in the API container.

## Run locally

Requirements: Python 3.11+, PostgreSQL, and Stockfish installed and available in `PATH`.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` to set a working PostgreSQL URL, a unique JWT secret, and the Stockfish executable path. Create the database and user in PostgreSQL, then:

```bash
uvicorn app.main:app --reload
```

On Windows, set `STOCKFISH_PATH` to the full path of `stockfish.exe` if it is not in PATH.

## Quick-start example

Register:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"player@example.com","password":"a-long-password-123"}'
```

Login (OAuth2 form uses `username` for the email):

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=player@example.com&password=a-long-password-123'
```

Copy `access_token` and use it below:

```bash
curl -X POST http://localhost:8000/games \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

curl -X POST http://localhost:8000/games/1/moves \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"uci":"e2e4","depth":14}'
```

## Tests

Tests use a temporary SQLite database, so the test suite does not require PostgreSQL. The Stockfish-dependent successful analysis path is deliberately not called in the base tests; add an integration test in an environment where Stockfish is installed.

```bash
pytest -q
```

## Security notes

- Passwords are hashed using bcrypt; raw passwords are never stored.
- JWTs expire; use HTTPS in production and keep the signing secret private.
- Game ownership is checked on every game-specific endpoint.
- SQLAlchemy parameterizes database operations.
- CORS is restricted to configured origins; replace defaults with your actual frontend origins.
- Login throttling, email verification, password reset, refresh-token rotation, audit logging, and database migrations (Alembic) should be added before public production deployment.
- Configure secrets through environment variables/secret manager. Never commit `.env`.
- Add reverse-proxy request limits and rate limits, especially on the CPU-intensive analysis endpoint.
- Set a conservative depth and use a queue/worker pool if many users can request analyses concurrently.

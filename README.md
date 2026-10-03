# SOMA Cube Puzzle Solver

A web application for building, solving, and exploring SOMA cube puzzles. It combines an interactive 3D interface with the [YASS](https://github.com/thanks4opensource/yass) text-based solver, user accounts, per-user progress tracking, and a hint system.

## Overview

The SOMA cube is a classic 3D puzzle made of 7 unique pieces that assemble into a 3x3x3 cube (and hundreds of other figures). With this app you can:

- Place, move, and rotate the seven SOMA pieces in a 3D scene
- Choose from 100+ target figures (cube, dog, pyramid, bathtub, and more)
- Check whether your arrangement is a valid solution
- Log in to save the solutions you discover and track your progress
- Request hints that place the next piece toward a solution you haven't found yet
- See how many solutions you've found out of the total for each figure, and how many hints you've used

## Features

### 3D puzzle interface
- Built with Three.js (loaded from a CDN through an import map)
- Orbit camera controls (drag to rotate, scroll to zoom)
- Keyboard controls for moving and rotating the selected piece
- The 3D canvas sizes itself to its container with a `ResizeObserver`, so it follows the window as it resizes

### Responsive single-screen layout
- On desktop, the whole app fits in the window with no page scrolling: header, controls, piece list and 3D view, and a bottom panel
- The bottom panel holds the solution counter, hint counter, and keyboard controls, and resizes with the window like the top panels
- On phone-sized screens (700px and below), page scrolling is allowed so the 3D view stays a usable size

### Accounts (Supabase Auth)
- Sign up, log in, and log out from the header
- Email confirmation on sign-up
- Friendly login errors ("No account found" vs. "Incorrect password") with a one-click password reset email
- Buttons have a 30-second cooldown to prevent spamming auth requests
- The backend verifies Supabase JWTs locally (no network call per request), using JWKS for modern RS256/ES256 projects and falling back to a shared secret for legacy HS256 projects
- Anonymous users can still play; solutions and hints just aren't saved

### Per-user progress
- Each valid, new solution is saved to the database against the logged-in user
- Solutions are normalized into a canonical string, so the same solution is recognized no matter how it was entered
- The "Solutions Found" counter shows your solutions out of the total for the selected figure (total comes from running YASS)
- The "Hints Used" counter tracks your hints across all puzzles
- A leaderboard endpoint ranks users by solutions found

### Hint system
- The backend uses a backtracking search to find a complete solution you haven't already found
- If your current pieces can't lead to a new solution, it temporarily ignores misplaced pieces (trying 1, 2, ... removals) and tells you which were adjusted
- The full solution is cached in the browser, so later hints in the same attempt are instant and skip the search
- The hinted piece is built directly from the backend's exact target cells, so the placement always matches the solution

### Rate limiting
- Flask-Limiter protects the API, with Redis as shared storage in production
- Falls back to in-memory counting when no `REDIS_URL` is set

## Project Structure

```
soma-solver/
├── backend/
│   ├── app.py                  # Flask server and API endpoints
│   ├── auth.py                 # Supabase JWT verification, email lookup
│   ├── config.py               # Environment-based configuration
│   ├── models.py               # SQLAlchemy models (User, Solution, HintEvent)
│   ├── scoring.py              # Per-user stats and leaderboard queries
│   ├── hint_solver.py          # Backtracking hint/solution search
│   ├── soma_grid.py            # .soma file parsing and grid conversion
│   ├── utils.py                # Solution validation and normalization
│   ├── migrate_solutions.py    # One-time import of legacy JSON solutions
│   ├── solutions/              # Legacy/global solution registry (JSON per figure)
│   └── yass/                   # YASS solver (cloned from GitHub)
├── frontend/
│   ├── index.html              # Main HTML interface
│   ├── style.css               # Application styling
│   └── js/
│       ├── main.js             # Application entry point
│       ├── constants.js        # Piece definitions and figure list
│       ├── gridManager.js      # Grid loading and cell state
│       ├── pieceManager.js     # Piece creation, movement, hint placement
│       ├── renderer.js         # Three.js scene, camera, resize handling
│       ├── uiController.js     # UI events and API calls
│       ├── authController.js   # Login/signup/logout UI and session handling
│       └── supabaseClient.js   # Supabase client, configured from /api/config
├── docker-compose.yml          # Redis for rate limiting
├── requirements.txt            # Python dependencies
└── README.md
```

## Setup and Installation

### Prerequisites

- Python 3.10+
- Git
- A [Supabase](https://supabase.com) project (for authentication)
- A C++ toolchain (to compile YASS)
- Docker (optional, for Redis)

### 1. Clone the repository

```
git clone https://github.com/macarreg/SomaCube.git
cd SomaCube
```

### 2. Compile the YASS solver

```
cd backend/yass
make
cd ../..
```

Try it out:

```
./soma -h
./soma -a figures/cube.soma
```

### 3. Install Python dependencies

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in `backend/`:

```
# Database (defaults to a local SQLite file if unset)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Flask
SECRET_KEY=change-me

# Supabase Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=            # only needed for legacy HS256 projects
SUPABASE_SERVICE_ROLE_KEY=      # server-side only, used for the login email check

# Rate limiting (optional; defaults to in-memory)
REDIS_URL=redis://localhost:6379

# Server port (optional; defaults to 8000)
PORT=8000
```

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | No | SQLAlchemy database URL. Defaults to `sqlite:///soma.db` |
| `SECRET_KEY` | Yes in production | Flask secret key |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Public key, sent to the browser through `/api/config` |
| `SUPABASE_JWT_SECRET` | Legacy only | Verifies HS256 tokens from older Supabase projects |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Enables the "no account" vs. "wrong password" login message |
| `REDIS_URL` | No | Shared rate-limit storage. Falls back to in-memory |
| `PORT` | No | Server port, default 8000 |

> **Never expose `SUPABASE_SERVICE_ROLE_KEY` to the frontend or commit your `.env` file.**

### 5. Start Redis (optional)

If you set `REDIS_URL`, start Redis first:

```
docker compose up -d
```

If you leave `REDIS_URL` unset, you can skip this step entirely for local development.

### 6. Create the database tables and import legacy solutions (optional)

Tables are created automatically on startup (`db.create_all()`). If you have older `solutions/*_solutions.json` files from before accounts existed, import them once:

```
cd backend
python migrate_solutions.py
```

### 7. Run the application

```
cd backend
python app.py
```

Open `http://localhost:8000`.

For production, use gunicorn:

```
cd backend
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

When running multiple workers, set `REDIS_URL` so rate limits are shared across them.

## How to Play

1. Pick a figure from the **Select Shape** dropdown.
2. Click a piece in the **Available Pieces** panel to add it to the scene.
3. Move and rotate it with the keyboard until it sits where you want.
4. Repeat until the figure is filled, then click **Check Solution**.
5. Log in to have new solutions saved to your account.
6. Stuck? Click **Hint** to have the next piece placed for you.

### Keyboard controls

| Key | Action |
|---|---|
| Arrow keys | Move piece in the X/Y plane |
| `Z` / `X` | Move piece in/out (Z axis) |
| `R` | Rotate around X axis |
| `F` | Rotate around Y axis |
| `V` | Rotate around Z axis |
| `Delete` | Remove selected piece |

### Buttons

| Button | Action |
|---|---|
| Check Solution | Validates the grid and saves the solution if it's new to you |
| Hint | Places the next piece toward a solution you haven't found |
| Reset Grid | Clears all pieces and reloads the figure |
| Remove Selected | Removes the currently selected piece |

## API Reference

All endpoints are under the Flask server. Authenticated requests send `Authorization: Bearer <supabase access token>`. A missing or invalid token is treated as anonymous.

| Method | Endpoint | Description | Rate limit |
|---|---|---|---|
| GET | `/api/config` | Public Supabase URL and anon key for the frontend | default |
| GET | `/api/shapes` | List available figures | default |
| GET | `/api/soma/<filename>` | Grid data for a `.soma` figure | default |
| POST | `/api/check-solution` | Validate (and save, if logged in) a solution | 30/min |
| POST | `/api/hint` | Compute or retrieve the next hint piece | 10/min |
| GET | `/api/solutions/<shape_id>` | Current user's solution count for a figure | default |
| GET | `/api/total-solutions/<shape_id>` | Total number of solutions for a figure (via YASS) | default |
| GET | `/api/stats/<shape_id>` | Current user's solutions found and hints used | default |
| GET | `/api/leaderboard` | Top users by solutions found (optional `?shape_id=`) | default |
| POST | `/api/auth/check-email` | Whether an account exists for an email | 5/min, 20/hr |
| GET | `/api/whoami` | Debug helper showing how your token is interpreted | default |

The default limit is 200 requests per hour per IP address.

## Data Model

| Table | Purpose |
|---|---|
| `users` | Local mirror of Supabase users (id, email, `hints_used`, timestamps), synced on each authenticated request |
| `solutions` | One row per user per discovered solution. Unique on `(user_id, shape_id, normalized_solution)` |
| `hint_events` | Hint usage events (user, shape, piece, timestamp) |

Solutions are stored in a canonical form: `z,y,x:piece` entries sorted and joined with `;`, shifted so the minimum coordinate is the origin.

## Architecture Notes

- **Two kinds of solution storage.** The `solutions/*.json` files are a *global* registry used by the hint solver so it never re-offers a known tiling. Per-user progress lives in the database. The counters shown to a user always come from the database.
- **Hint placement.** The backend returns the exact absolute target cells for a piece. The frontend builds the piece directly from those cells with no rotation, rather than searching for a matching rotation, so placement is always exact.
- **Frontend dependencies.** Three.js and the Supabase client are loaded from a CDN via the import map in `index.html`, so `npm install` is not required to run the app.
- **Supabase keys.** Only the anon key reaches the browser. The service role key stays on the server.

## Docker

The included `docker-compose.yml` runs Redis, which the rate limiter uses to share counters across gunicorn workers:

```
docker compose up -d     # start Redis
docker compose down      # stop Redis
```

### Troubleshooting: 500 errors when Docker is stopped

If `REDIS_URL` points at the Redis container and Docker is paused or stopped, the rate limiter can't reach its storage and every request fails with a 500 (every route is rate limited). Either start Docker, remove `REDIS_URL` from your local `.env`, or make the limiter degrade gracefully:

```python
limiter = Limiter(
    get_remote_address, app=app, headers_enabled=True,
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    default_limits=["200 per hour"],
    swallow_errors=True,
    in_memory_fallback_enabled=True,
)
```

### Containerizing the app (optional)

If you deploy with Docker, keep these points in mind:

- Compile YASS *inside* the image (`make` in `backend/yass`); a binary built on macOS or Windows won't run on Linux
- Mount `backend/solutions` as a volume so the global solution registry survives rebuilds
- Pass secrets with `env_file` rather than baking them into the image
- Add a `.dockerignore` for `node_modules`, `venv`, `.env`, `__pycache__`, and `*.db`

## Development Notes

- `app.py` runs with `debug=False`. Set it temporarily while developing if you want the Flask reloader.
- `db.create_all()` is fine for development. Switch to migrations (for example Alembic) once the schema needs to change on a live database.
- Logging is set to DEBUG level by default; lower it for production.
- A few figures are not solvable (for example `eiffel`), so their totals will be zero.

## Future Plans

- Library of classic SOMA cube challenges
- Leaderboard UI
- Collapsible piece list for a no-scroll layout on phones
- Dockerfile and deployment guide
- Additional puzzle statistics and analysis tools

## Credits

- [YASS SOMA Cube Solver](https://github.com/thanks4opensource/yass), the solver engine used by this project, developed by Mark R. Rubin
- [Three.js](https://threejs.org) for 3D rendering
- [Supabase](https://supabase.com) for authentication

## License

This project integrates the YASS SOMA Cube Solver, which is licensed under the GNU General Public License v3.0. As a derivative work, this project is also licensed under GPL-3.0. You may copy, distribute, and modify it under the terms of that license. A full copy of the license is in the LICENSE file.
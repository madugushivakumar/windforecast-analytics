# Deployment Guide: WindForecast Analytics

This guide details how to deploy the WindForecast Analytics platform to production environments using **Vercel** (for the React frontend) and **Heroku / Render / Docker Host** (for the FastAPI Python backend).

---

## 1. Architecture & Hosting Strategy
```
[User Browser]
       │
       ├─► [Vercel CDN] ───────────────► React SPA (Static assets + client routing)
       │                                     │
       └─► [Heroku / Cloud Container] ◄──────┘ REST Requests (/api/*, /health)
                 │
                 ▼
          [Elexon BMRS API]
```

---

## 2. Backend Deployment (Heroku or Render)

### Option A: Heroku Deployment
1. **Prerequisites**: Heroku CLI installed and an active Heroku account.
2. **Create Heroku App**:
   ```bash
   cd backend
   heroku create windforecast-analytics-api
   ```
3. **Configure Buildpack or Container**:
   Heroku automatically detects `requirements.txt`.
   Add a `Procfile` in `backend/Procfile`:
   ```text
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
4. **Set Environment Variables**:
   ```bash
   heroku config:set ENVIRONMENT=production
   heroku config:set ELEXON_API_BASE_URL=https://data.elexon.co.uk/bmrs/api/v1
   heroku config:set CORS_ORIGINS=https://windforecast-analytics.vercel.app,http://localhost:3000
   heroku config:set DEFAULT_CUTOFF_HOUR_UTC=11
   heroku config:set ENABLE_CACHE=true
   ```
5. **Deploy Code** (from current `master` branch):
   ```bash
   git subtree push --prefix backend heroku master:main
   ```
6. **Verify Health Endpoint**:
   ```bash
   curl -f https://windforecast-analytics-api.herokuapp.com/health
   ```

### Option B: Render or Cloud Container Deployment
1. Connect repository to Render or Railway.
2. Select **Docker Service** and specify `backend/Dockerfile` as the Dockerfile path.
3. Configure environment variables as described above.

---

## 3. Frontend Deployment (Vercel)

1. **Install Vercel CLI** (or connect via GitHub):
   ```bash
   npm install -g vercel
   ```
2. **Deploy from `frontend/` directory**:
   ```bash
   cd frontend
   vercel --prod
   ```
3. **Configure Environment Variables on Vercel Dashboard**:
   - `VITE_API_BASE_URL`: The deployed backend URL (e.g. `https://windforecast-analytics-api.herokuapp.com`).
4. **Build & Output Settings**:
   - Framework Preset: `Vite`
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm install`
5. **Client-Side Routing (`vercel.json`)**:
   Ensure `vercel.json` in `frontend/` handles SPA rewrites:
   ```json
   {
     "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
   }
   ```

---

## 4. Local Container Deployment (Docker Compose)

The repository provides production-ready container configurations for both services:
- `backend/Dockerfile`: Multi-layer Python 3.11-slim container with non-root app structure and cache mount.
- `frontend/Dockerfile`: Multi-stage build (Node 20 build stage -> Nginx 1.25 Alpine runtime stage with custom reverse proxy).
- `docker-compose.yml`: Coordinates services, environment variables, healthchecks, and host volume caching (`./backend/data/cache:/app/data/cache`).

### Configuration Validation
Syntax and volume mapping can be statically validated using:
```bash
docker compose config
```
*(Verified: valid Compose specification, zero syntax errors).*

### Build & Run Execution
Once the Docker Desktop daemon is started on the host machine:
```bash
# 1. Clean build of images
docker compose build --no-cache

# 2. Start all services in the background
docker compose up -d

# 3. Verify running services
docker compose ps

# 4. Check backend and frontend logs
docker compose logs --tail=100

# 5. Verify local endpoints
curl -f http://localhost:8000/health
curl -f http://localhost:8000/api/overview
curl -f http://localhost:3000/

# 6. Clean shutdown (preserving disk cache)
docker compose down
```

*Note on Local Runtime Status*: If `com.docker.service` is stopped on Windows, start Docker Desktop via the Windows Start Menu or run PowerShell with Administrator privileges (`Start-Service com.docker.service`) to initialize the `dockerDesktopLinuxEngine` named pipe.

---

## 5. Pre-Deployment Verification Checklist

- [x] Backend tests pass (`python -m pytest backend/tests -v`).
- [x] Frontend tests pass (`npm run test` in `frontend/`).
- [x] Frontend builds with zero TypeScript errors (`npm run build`).
- [x] Health endpoint distinguishes app health from upstream Elexon status.
- [x] CORS allows production frontend origin.
- [x] No secrets, private tokens, or `.env` files are tracked in git.
- [x] Downloadable CSV export serves verified records with proper `Content-Disposition`.
- [ ] Public URLs tested in an incognito browser window (Pending user hosting deployment & authorization).

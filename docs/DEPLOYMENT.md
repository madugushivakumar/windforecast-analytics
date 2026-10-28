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
5. **Deploy Code**:
   ```bash
   git subtree push --prefix backend heroku main
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

To run both services locally in isolated Docker containers:
```bash
# Start Docker Desktop daemon first, then run:
docker compose up --build

# Backend will be available at: http://localhost:8000
# Frontend will be available at: http://localhost:3000
# Health check: http://localhost:8000/health
# Swagger Docs: http://localhost:8000/docs

# To stop:
docker compose down
```

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

# Acme Logistics Carrier API

FastAPI backend for the HappyRobot inbound carrier sales agent.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /loads/search | Search loads by lane + equipment |
| GET | /carrier/verify | Verify carrier MC number via FMCSA |
| POST | /calls/log | Log a completed call |
| GET | /calls | Get all call logs |
| GET | /dashboard/metrics | Get aggregated metrics |

All endpoints (except /health) require header: `X-API-Key: acme-secret-key-123`

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Visit http://localhost:8000/docs for the interactive API docs.

## Run with Docker

```bash
docker-compose up --build
```

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Set environment variables:
   - API_KEY=acme-secret-key-123
   - FMCSA_KEY=your_fmcsa_webkey
4. Railway auto-detects the Dockerfile and deploys
5. Copy the generated URL (e.g. https://freight-api.up.railway.app)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| API_KEY | Secret key for all endpoints | acme-secret-key-123 |
| FMCSA_KEY | FMCSA webkey for carrier verification | (mock mode if empty) |

## HappyRobot Tool URLs

Once deployed, use these URLs in your HappyRobot tool nodes:

- verify_carrier: `GET https://your-url.railway.app/carrier/verify?mc_number={mc_number}`
- search_loads: `GET https://your-url.railway.app/loads/search?origin={origin}&destination={destination}&equipment_type={equipment_type}`
- log call (HTTP node): `POST https://your-url.railway.app/calls/log`

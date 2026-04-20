from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import httpx
import os
from datetime import datetime

app = FastAPI(title="Acme Logistics Carrier API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth ---
API_KEY = os.getenv("API_KEY", "acme-secret-key-123")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key

# --- Load Data ---
with open("loads.json") as f:
    LOADS = json.load(f)

# --- In-memory call log (persists while server is running) ---
CALL_LOGS = []

# --- Models ---
class CallLog(BaseModel):
    carrier_mc: Optional[str] = None
    carrier_verified: Optional[str] = None
    lane_origin: Optional[str] = None
    lane_destination: Optional[str] = None
    load_id: Optional[str] = None
    loadboard_rate: Optional[float] = None
    carrier_initial_offer: Optional[float] = None
    final_agreed_rate: Optional[float] = None
    negotiation_rounds: Optional[int] = None
    call_outcome: Optional[str] = None
    carrier_sentiment: Optional[str] = None
    key_notes: Optional[str] = None

# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/loads/search", dependencies=[Depends(verify_api_key)])
def search_loads(
    origin: str = Query(..., description="Origin city or state"),
    destination: str = Query(..., description="Destination city or state"),
    equipment_type: str = Query(..., description="Equipment type: dry van, reefer, flatbed")
):
    origin_l = origin.lower()
    dest_l = destination.lower()
    equip_l = equipment_type.lower()

    scored = []
    for load in LOADS:
        o_match = any(w in load["origin"].lower() for w in origin_l.split())
        d_match = any(w in load["destination"].lower() for w in dest_l.split())
        e_match = equip_l in load["equipment_type"].lower()

        score = (o_match * 2) + (d_match * 2) + (e_match * 3)
        if score > 0:
            scored.append((score, load))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return {"found": False, "message": "No loads found for that lane.", "loads": []}

    return {
        "found": True,
        "loads": [r[1] for r in scored[:3]]
    }


@app.get("/carrier/verify", dependencies=[Depends(verify_api_key)])
async def verify_carrier(mc_number: str = Query(...)):
    fmcsa_key = os.getenv("FMCSA_KEY", "")

    if not fmcsa_key:
        return {"eligible": True, "carrier_name": "Mock Carrier", "mc_number": mc_number, "source": "mock"}

    url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/{mc_number}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={"webKey": fmcsa_key}, timeout=10)
            raw = resp.text
            data = resp.json()
            carrier = data.get("content", {}).get("carrier", {})
            allowed = carrier.get("allowedToOperate", "N")
            return {
                "eligible": allowed == "Y",
                "carrier_name": carrier.get("legalName", "Unknown"),
                "mc_number": mc_number,
                "operating_status": carrier.get("operatingStatus", "Unknown"),
                "raw_response": data,
                "source": "fmcsa"
            }
        except Exception as e:
            return {
                "eligible": None,
                "error": str(e),
                "mc_number": mc_number,
                "source": "error"
            }


@app.post("/calls/log", dependencies=[Depends(verify_api_key)])
def log_call(call: CallLog):
    entry = call.dict()
    entry["id"] = len(CALL_LOGS) + 1
    entry["logged_at"] = datetime.utcnow().isoformat()
    CALL_LOGS.append(entry)
    return {"success": True, "call_id": entry["id"], "total_calls": len(CALL_LOGS)}


@app.get("/calls", dependencies=[Depends(verify_api_key)])
def get_calls():
    return {"calls": CALL_LOGS, "total": len(CALL_LOGS)}


@app.get("/dashboard/metrics", dependencies=[Depends(verify_api_key)])
def get_metrics():
    total = len(CALL_LOGS)
    if total == 0:
        return {
            "total_calls": 0,
            "booking_rate_pct": 0,
            "total_revenue": 0,
            "avg_rate": 0,
            "outcomes": {},
            "sentiments": {},
            "avg_negotiation_rounds": 0
        }

    outcomes = {}
    sentiments = {}
    booked_rates = []
    negotiation_rounds = []

    for c in CALL_LOGS:
        outcome = c.get("call_outcome") or "unknown"
        sentiment = c.get("carrier_sentiment") or "unknown"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        sentiments[sentiment] = sentiments.get(sentiment, 0) + 1

        if outcome == "booked_transferred" and c.get("final_agreed_rate"):
            booked_rates.append(c["final_agreed_rate"])

        if c.get("negotiation_rounds") is not None:
            negotiation_rounds.append(c["negotiation_rounds"])

    return {
        "total_calls": total,
        "booking_rate_pct": round(len(booked_rates) / total * 100, 1),
        "total_revenue": round(sum(booked_rates), 2),
        "avg_rate": round(sum(booked_rates) / len(booked_rates), 2) if booked_rates else 0,
        "avg_negotiation_rounds": round(sum(negotiation_rounds) / len(negotiation_rounds), 1) if negotiation_rounds else 0,
        "outcomes": outcomes,
        "sentiments": sentiments,
        "recent_calls": CALL_LOGS[-5:]
    }

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

# --- City coordinates for directional search ---
CITY_COORDS = {
    "dallas": (32.7, -96.8), "houston": (29.7, -95.4), "chicago": (41.8, -87.6),
    "atlanta": (33.7, -84.4), "miami": (25.7, -80.2), "los angeles": (34.0, -118.2),
    "seattle": (47.6, -122.3), "denver": (39.7, -104.9), "phoenix": (33.4, -112.0),
    "new york": (40.7, -74.0), "boston": (42.3, -71.0), "nashville": (36.1, -86.7),
    "memphis": (35.1, -90.0), "kansas city": (39.0, -94.5), "minneapolis": (44.9, -93.2),
    "portland": (45.5, -122.6), "san francisco": (37.7, -122.4), "detroit": (42.3, -83.0),
    "charlotte": (35.2, -80.8), "philadelphia": (39.9, -75.1), "columbus": (39.9, -82.9),
    "indianapolis": (39.7, -86.1), "louisville": (38.2, -85.7), "cincinnati": (39.1, -84.5),
    "pittsburgh": (40.4, -79.9), "st. louis": (38.6, -90.2), "new orleans": (29.9, -90.0),
    "san antonio": (29.4, -98.4), "oklahoma city": (35.4, -97.5), "albuquerque": (35.0, -106.6),
    "el paso": (31.7, -106.4), "las vegas": (36.1, -115.1), "salt lake city": (40.7, -111.8),
    "boise": (43.6, -116.2), "omaha": (41.2, -96.0), "milwaukee": (43.0, -87.9),
    "raleigh": (35.7, -78.6), "jacksonville": (30.3, -81.6), "tampa": (27.9, -82.4),
    "fresno": (36.7, -119.7), "sacramento": (38.5, -121.4), "portland": (45.5, -122.6),
}

STATE_ABBREV = {
    "illinois": "il", "texas": "tx", "florida": "fl", "georgia": "ga",
    "california": "ca", "new york": "ny", "ohio": "oh", "michigan": "mi",
    "tennessee": "tn", "arizona": "az", "colorado": "co", "washington": "wa",
    "oregon": "or", "nevada": "nv", "minnesota": "mn", "missouri": "mo",
    "louisiana": "la", "alabama": "al", "pennsylvania": "pa", "virginia": "va",
    "north carolina": "nc", "south carolina": "sc", "indiana": "in",
    "wisconsin": "wi", "kansas": "ks", "nebraska": "ne", "utah": "ut",
    "idaho": "id", "montana": "mt", "wyoming": "wy", "new mexico": "nm",
}

def get_origin_coords(origin: str):
    origin_l = origin.lower()
    for city, coords in CITY_COORDS.items():
        if city in origin_l:
            return coords
    return None

def get_dest_coords(dest: str):
    dest_l = dest.lower()
    for city, coords in CITY_COORDS.items():
        if city in dest_l:
            return coords
    return None

def is_directional_match(origin: str, load_dest: str, direction: str) -> bool:
    origin_coords = get_origin_coords(origin)
    if not origin_coords:
        return True  # can't determine, allow
    dest_coords = get_dest_coords(load_dest)
    if not dest_coords:
        return True  # can't determine, allow
    lat_diff = dest_coords[0] - origin_coords[0]
    lng_diff = dest_coords[1] - origin_coords[1]
    if "north" in direction:
        return lat_diff > 1
    if "south" in direction:
        return lat_diff < -1
    if "east" in direction:
        return lng_diff > 1
    if "west" in direction:
        return lng_diff < -1
    return True

# --- Models ---
class CallLog(BaseModel):
    carrier_mc: Optional[str] = None
    carrier_verified: Optional[str] = None
    lane_origin: Optional[str] = None
    lane_destination: Optional[str] = None
    load_id: Optional[str] = None
    loadboard_rate: Optional[str] = None
    carrier_initial_offer: Optional[str] = None
    final_agreed_rate: Optional[str] = None
    negotiation_rounds: Optional[str] = None
    call_outcome: Optional[str] = None
    carrier_sentiment: Optional[str] = None
    key_notes: Optional[str] = None

    def to_log(self):
        def safe_float(v):
            try: return float(v)
            except: return None
        def safe_int(v):
            try: return int(v)
            except: return None
        return {
            "carrier_mc": self.carrier_mc,
            "carrier_verified": self.carrier_verified,
            "lane_origin": self.lane_origin,
            "lane_destination": self.lane_destination,
            "load_id": self.load_id,
            "loadboard_rate": safe_float(self.loadboard_rate),
            "carrier_initial_offer": safe_float(self.carrier_initial_offer),
            "final_agreed_rate": safe_float(self.final_agreed_rate),
            "negotiation_rounds": safe_int(self.negotiation_rounds),
            "call_outcome": self.call_outcome,
            "carrier_sentiment": self.carrier_sentiment,
            "key_notes": self.key_notes,
        }

# --- Endpoints ---

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    with open("dashboard.html") as f:
        return f.read()


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/loads/search", dependencies=[Depends(verify_api_key)])
def search_loads(
    origin: str = Query(..., description="Origin city or state"),
    equipment_type: str = Query(..., description="Equipment type: dry van, reefer, flatbed"),
    destination: Optional[str] = Query(None, description="Destination city, state, or direction. Optional.")
):
    import re

    def clean_words(text):
        return [re.sub(r'[^a-z0-9]', '', w) for w in text.lower().split() if len(w) >= 3]

    origin_l = origin.lower().strip()
    equip_l = equipment_type.lower().strip()
    dest_l = destination.lower().strip() if destination else ""

    for full, abbr in STATE_ABBREV.items():
        if full in origin_l:
            origin_l = origin_l.replace(full, abbr)
        if dest_l and full in dest_l:
            dest_l = dest_l.replace(full, abbr)

    origin_words = clean_words(origin_l)
    dest_words = clean_words(dest_l) if dest_l else []

    directions = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
    is_directional = dest_l and any(d in dest_l for d in directions)

    scored = []
    for load in LOADS:
        load_origin = load["origin"].lower()
        load_dest = load["destination"].lower()
        load_equip = load["equipment_type"].lower()

        load_origin_words = clean_words(load_origin)
        load_dest_words = clean_words(load_dest)

        o_match = any(w in load_origin_words for w in origin_words) if origin_words else False
        if not o_match:
            continue

        if not dest_l:
            d_match = True
        elif is_directional:
            d_match = is_directional_match(origin, load["destination"], dest_l)
        else:
            d_match = any(w in load_dest_words for w in dest_words) if dest_words else True

        e_match = equip_l in load_equip
        score = (o_match * 2) + (d_match * 2) + (e_match * 2)
        scored.append((score, load))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return {"found": False, "message": "No loads found from that origin.", "loads": []}

    return {"found": True, "loads": [r[1] for r in scored[:3]]}


@app.get("/carrier/verify", dependencies=[Depends(verify_api_key)])
async def verify_carrier(mc_number: str = Query(...)):
    clean = mc_number.upper().replace("MC", "").replace("-", "").strip()

    demo_carriers = {
        "23569": {"name": "Werner Enterprises", "status": "AUTHORIZED FOR HIRE", "eligible": True},
        "96382": {"name": "JB Hunt Transport", "status": "AUTHORIZED FOR HIRE", "eligible": True},
        "15735": {"name": "Swift Transportation", "status": "AUTHORIZED FOR HIRE", "eligible": True},
        "00000": {"name": "Revoked Carrier Inc", "status": "OUT OF SERVICE", "eligible": False},
        "11111": {"name": "Suspended Carrier LLC", "status": "SUSPENDED", "eligible": False},
    }

    if clean in demo_carriers:
        c = demo_carriers[clean]
        return {"eligible": c["eligible"], "carrier_name": c["name"], "mc_number": mc_number, "operating_status": c["status"], "source": "fmcsa_override"}

    fmcsa_key = os.getenv("FMCSA_KEY", "")
    if fmcsa_key:
        url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/{clean}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params={"webKey": fmcsa_key}, headers={"Accept": "application/json"}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    carrier = data.get("content", {}).get("carrier", {})
                    if carrier:
                        allowed = carrier.get("allowedToOperate", "N")
                        return {"eligible": allowed == "Y", "carrier_name": carrier.get("legalName", "Unknown"), "mc_number": mc_number, "operating_status": carrier.get("operatingStatus", "Unknown"), "source": "fmcsa"}
            except Exception:
                pass

    if len(clean) >= 4:
        return {"eligible": True, "carrier_name": "Verified Carrier LLC", "mc_number": mc_number, "operating_status": "AUTHORIZED FOR HIRE", "source": "mock"}

    return {"eligible": False, "carrier_name": None, "mc_number": mc_number, "operating_status": "NOT FOUND", "source": "mock"}


@app.post("/calls/log", dependencies=[Depends(verify_api_key)])
def log_call(call: CallLog):
    entry = call.to_log()
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
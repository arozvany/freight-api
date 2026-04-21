"""
Seed script to populate the dashboard with realistic demo call data.
Usage: python3 seed_data.py
"""

import requests
import random
from datetime import datetime, timedelta

API_BASE = "https://freight-api-production.up.railway.app"
API_KEY = "acme-secret-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

CARRIERS = ["23569", "96382", "15735", "78234", "44521", "91023"]
ORIGINS = ["Chicago, IL", "Dallas, TX", "Atlanta, GA", "Houston, TX", "Los Angeles, CA", "Nashville, TN", "Memphis, TN", "Denver, CO"]
DESTINATIONS = ["Dallas, TX", "Miami, FL", "Phoenix, AZ", "Seattle, WA", "Chicago, IL", "Atlanta, GA", "Houston, TX", "Kansas City, MO"]
EQUIPMENT = ["dry van", "reefer", "flatbed"]
LOAD_IDS = ["LD001", "LD002", "LD003", "LD004", "LD005", "LD007", "LD009", "LD010"]
LOADBOARD_RATES = [950, 1200, 1600, 1950, 2200, 2600, 2800, 3200, 3800]

OUTCOMES = [
    "booked_transferred",
    "booked_transferred",
    "booked_transferred",
    "negotiation_failed",
    "presented_not_interested",
    "no_load_found",
    "declined_unverified",
]

SENTIMENTS = ["positive", "positive", "neutral", "neutral", "negative"]

def make_call(days_ago=0):
    outcome = random.choice(OUTCOMES)
    sentiment = random.choice(SENTIMENTS)
    equipment = random.choice(EQUIPMENT)
    origin = random.choice(ORIGINS)
    destination = random.choice(DESTINATIONS)
    lb_rate = random.choice(LOADBOARD_RATES)
    rounds = 0

    carrier_initial = None
    final_rate = None

    if outcome == "booked_transferred":
        rounds = random.randint(0, 3)
        carrier_initial = lb_rate + random.randint(100, 500) if rounds > 0 else None
        uplift = random.uniform(0, 0.10)
        final_rate = round(lb_rate * (1 + uplift), 2) if rounds > 0 else lb_rate
        sentiment = random.choice(["positive", "positive", "neutral"])

    elif outcome == "negotiation_failed":
        rounds = 3
        carrier_initial = lb_rate + random.randint(400, 800)
        final_rate = None
        sentiment = random.choice(["negative", "neutral"])

    elif outcome == "declined_unverified":
        origin = None
        destination = None
        equipment = None
        sentiment = "neutral"

    return {
        "carrier_mc": random.choice(CARRIERS),
        "carrier_verified": "false" if outcome == "declined_unverified" else "true",
        "lane_origin": origin,
        "lane_destination": destination,
        "load_id": random.choice(LOAD_IDS) if outcome not in ["declined_unverified", "no_load_found"] else None,
        "equipment_type": equipment,
        "loadboard_rate": str(lb_rate),
        "carrier_initial_offer": str(carrier_initial) if carrier_initial else "",
        "final_agreed_rate": str(final_rate) if final_rate else "",
        "negotiation_rounds": str(rounds),
        "call_outcome": outcome,
        "carrier_sentiment": sentiment,
        "key_notes": "Seeded demo data"
    }

def seed(count=20):
    print(f"Seeding {count} calls to {API_BASE}...")
    success = 0
    for i in range(count):
        days_ago = random.randint(0, 7)
        data = make_call(days_ago)
        resp = requests.post(f"{API_BASE}/calls/log", json=data, headers=HEADERS)
        if resp.status_code == 200:
            success += 1
            print(f"  ✓ Call {i+1}: {data['call_outcome']} — {data['lane_origin']} → {data['lane_destination']}")
        else:
            print(f"  ✗ Call {i+1} failed: {resp.text}")

    print(f"\nDone — {success}/{count} calls seeded successfully.")
    print(f"Dashboard: {API_BASE}/dashboard")

if __name__ == "__main__":
    seed(20)
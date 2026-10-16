#!/usr/bin/env python3
"""Seed a running API with synthetic OTT events and process them.

All data is synthetic: subscriber, device and title IDs are generated, and IP
addresses come from the RFC 5737 documentation ranges, which never belong to
real users.

Usage:
    python src/scripts/seed_demo.py --base-url http://127.0.0.1:8101 --events 240
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta

import requests

DOC_NETS = ["192.0.2", "198.51.100", "203.0.113"]

# region code -> (weight, is_eu, consent rate)
REGIONS = {
    "US": (30, False, 0.97),
    "DE": (14, True, 0.85),
    "FR": (10, True, 0.80),
    "EU": (6, True, 0.75),
    "CA": (10, False, 0.92),
    "BR": (10, False, 0.90),
    "JP": (8, False, 1.00),
}

PLAYBACK = ["play", "play", "play", "pause", "seek", "stop"]


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def home_region(user: int) -> str:
    """Each synthetic subscriber has a stable home market."""
    r = random.Random(user)
    return r.choices(list(REGIONS), weights=[v[0] for v in REGIONS.values()])[0]


def make_event(rng: random.Random, n: int, now: datetime) -> dict:
    user = rng.randint(1, 60)
    region = home_region(user)
    _, is_eu, consent_rate = REGIONS[region]
    roll = rng.random()
    extra: dict = {"app_version": f"5.{rng.randint(0, 3)}.{rng.randint(0, 9)}"}
    if roll < 0.12:
        event_type = "ad_impression"
        extra["targeted"] = rng.random() < 0.6
        extra["gpc"] = region == "US" and rng.random() < 0.5
    elif roll < 0.17:
        event_type = rng.choice(["error", "login_failed"])
    elif roll < 0.22:
        event_type = "login"
    else:
        event_type = rng.choice(PLAYBACK)
    return {
        "event_id": f"evt-{n:05d}",
        "user_id": f"sub-{user:04d}",
        "device_id": f"tv-{user:04d}",
        "content_id": f"title-{rng.randint(1, 40):03d}",
        "event_type": event_type,
        "timestamp": iso(now - timedelta(minutes=rng.randint(5, 360))),
        "region": region,
        "is_eu": is_eu,
        "has_consent": rng.random() < consent_rate,
        "ip_address": f"{rng.choice(DOC_NETS)}.{rng.randint(1, 254)}",
        "subscription_plan": rng.choice(["basic", "premium"]),
        "extra_metadata": extra,
    }


def risky_patterns(start: int, now: datetime) -> list[dict]:
    """A few deliberate patterns the rules should catch."""
    events = []
    n = start
    # One account streaming from four markets within the same hour.
    for i, region in enumerate(["US", "DE", "BR", "JP", "US", "DE"]):
        events.append(
            {
                "event_id": f"evt-{n:05d}",
                "user_id": "sub-0900",
                "device_id": f"tv-09{i:02d}",
                "content_id": "title-007",
                "event_type": "play",
                "timestamp": iso(now - timedelta(minutes=50 - i * 5)),
                "region": region,
                "is_eu": region == "DE",
                "has_consent": True,
                "ip_address": f"203.0.113.{200 + i}",
                "subscription_plan": "basic",
            }
        )
        n += 1
    # Six accounts sharing one device (account sharing / resale pattern).
    for i in range(6):
        events.append(
            {
                "event_id": f"evt-{n:05d}",
                "user_id": f"sub-08{i:02d}",
                "device_id": "tv-shared-01",
                "content_id": "title-012",
                "event_type": "play",
                "timestamp": iso(now - timedelta(minutes=30 + i)),
                "region": "FR",
                "is_eu": True,
                "has_consent": i % 2 == 0,
                "ip_address": "198.51.100.77",
                "subscription_plan": "basic",
            }
        )
        n += 1
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--events", type=int, default=240)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    now = datetime.now(UTC)
    events = [make_event(rng, i, now) for i in range(args.events)]
    events += risky_patterns(args.events, now)

    s = requests.Session()
    accepted = 0
    for ev in events:
        r = s.post(f"{args.base_url}/events", json=ev, timeout=10)
        accepted += r.status_code == 202
    print(f"accepted {accepted}/{len(events)} events")

    token = s.post(
        f"{args.base_url}/token",
        data={"username": args.username, "password": args.password},
        timeout=10,
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    processed = s.post(f"{args.base_url}/process/drain", headers=headers, timeout=120).json()
    print(f"processed {len(processed)} events")
    summary = s.get(f"{args.base_url}/compliance/summary", headers=headers, timeout=10).json()
    print("risk summary:", summary)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export a JSON fixture for the static live demo by running the real pipeline.

Nothing in the fixture is invented in the browser. This script:

1. Builds synthetic events with the same generator as ``src/scripts/seed_demo.py``.
2. Sends them through the real FastAPI app (``POST /events`` then
   ``POST /process/drain``) using an in-process test client and a throwaway
   SQLite database in a temp directory, so no database file lands in the repo.
3. Builds a synthetic queue of data-subject deletion requests and checks each
   one with ``RegulationFramework.check_violation("data_deletion", ...)``, the
   deadline rule modeled in ``src/app/regulations.py``.
4. Writes everything to ``demo/site/data/fixture.json``.

Usage:
    python demo/export_fixture.py [--events 360] [--seed 7] [--out demo/site/data/fixture.json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import random
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "demo" / "site" / "data" / "fixture.json"

# Requests this close to the statutory deadline are shown as "at risk". This is
# a dashboard convention for the demo, not part of the regulation rules.
AT_RISK_WINDOW_DAYS = 7


def _isolate_storage() -> str:
    """Point the app at a temp database and model dir before it is imported."""
    tmp = tempfile.mkdtemp(prefix="ottc-demo-")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/demo.db"
    os.environ["MODEL_DIR"] = os.path.join(tmp, "models")
    os.environ.setdefault("REDIS_HOST", "127.0.0.1")
    return tmp


def _load_seed_module():
    path = ROOT / "src" / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _deletion_requests(seed_mod, rng: random.Random, now: datetime, count: int) -> list[dict]:
    from src.app.regulations import RegulationFramework

    requests_out = []
    for i in range(count):
        user = rng.randint(1, 60)
        region = seed_mod.home_region(user)
        received = now - timedelta(days=rng.uniform(1, 58), hours=rng.randint(0, 23))
        # Most requests close within two weeks; a tail drags past the deadline.
        if rng.random() < 0.72:
            duration = min(rng.triangular(2, 44, 11), 58)
            completed = received + timedelta(days=duration)
            if completed > now:
                completed = None
        else:
            completed = None
        end = completed or now
        elapsed_days = (end - received).total_seconds() / 86400
        regs = RegulationFramework.get_regulations_for_region(region)
        checks = [
            RegulationFramework.check_violation("data_deletion", r, {"deletion_time_days": elapsed_days})
            for r in regs
        ]
        breached = any(c["violation"] for c in checks)
        deadline_days = 30  # the deadline check_violation applies today
        if not regs:
            status = "no_rule"
        elif breached:
            status = "breached"
        elif completed is None and elapsed_days >= deadline_days - AT_RISK_WINDOW_DAYS:
            status = "at_risk"
        else:
            status = "on_time"
        requests_out.append(
            {
                "id": f"dsr-{i + 1:04d}",
                "user_id": f"sub-{user:04d}",
                "region": region,
                "regulations": [r.value for r in regs],
                "received": seed_mod.iso(received),
                "completed": seed_mod.iso(completed) if completed else None,
                "elapsed_days": round(elapsed_days, 1),
                "deadline_days": deadline_days,
                "state": "closed" if completed else "open",
                "status": status,
                "reasons": [c["reason"] for c in checks if c["violation"]],
            }
        )
    requests_out.sort(key=lambda r: r["received"], reverse=True)
    return requests_out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", type=int, default=360)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--deletions", type=int, default=64)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    logging.disable(logging.WARNING)
    _isolate_storage()
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    from src.app.main import app
    from src.app.regulations import ComplianceChecker, RegulationFramework

    seed_mod = _load_seed_module()
    rng = random.Random(args.seed)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    events = [seed_mod.make_event(rng, i, now) for i in range(args.events)]
    events += seed_mod.risky_patterns(args.events, now)

    with TestClient(app) as client:
        accepted = sum(client.post("/events", json=ev).status_code == 202 for ev in events)
        token = client.post("/token", data={"username": "admin", "password": "admin123"}).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        processed = client.post("/process/drain", headers=headers).json()
        summary = client.get("/compliance/summary", headers=headers).json()

    rows = []
    for item in processed:
        ev, res = item["event"], item.get("result")
        if res is None:
            continue
        extra = ev.get("extra_metadata") or {}
        check = res["detailed_findings"].get("compliance_check", {})
        rows.append(
            {
                "id": ev["event_id"],
                "user": ev["user_id"],
                "device": ev["device_id"],
                "content": ev["content_id"],
                "type": ev["event_type"],
                "ts": ev["timestamp"],
                "region": ev["region"],
                "is_eu": ev["is_eu"],
                "consent": ev["has_consent"],
                "gpc": bool(extra.get("gpc")),
                "targeted": bool(extra.get("targeted")),
                "plan": ev.get("subscription_plan"),
                "score": res["score"],
                "risk": res["risk_level"],
                "flags": res["flags"],
                "regs": check.get("applicable_regulations", []),
                "violations": [
                    {"regulation": v["regulation"], "action": v["action"], "reason": v["reason"]}
                    for v in check.get("violations", [])
                ],
            }
        )
    rows.sort(key=lambda r: r["ts"], reverse=True)

    regions_seen = sorted({r["region"] for r in rows})
    fixture = {
        "meta": {
            "generated_at": seed_mod.iso(now),
            "seed": args.seed,
            "events_sent": len(events),
            "events_accepted": accepted,
            "events_processed": len(rows),
            "risk_summary": summary,
            "at_risk_window_days": AT_RISK_WINDOW_DAYS,
            "source": "src/scripts/seed_demo.py generator -> POST /events -> POST /process/drain",
        },
        "rules": {
            # The exact tables the Python rules use, so the browser simulator
            # applies the same mapping instead of a hand-copied one.
            "region_regulations": {
                region: [r.value for r in regs]
                for region, regs in RegulationFramework.REGION_REGULATIONS.items()
            },
            "requirements": {
                reg.value: req for reg, req in RegulationFramework.REGULATION_REQUIREMENTS.items()
            },
            "event_actions": {
                t: ComplianceChecker()._map_event_to_action(t)
                for t in ["play", "pause", "stop", "seek", "login", "ad_impression", "logout", "error"]
            },
            "regions_seen": regions_seen,
        },
        "events": rows,
        "deletion_requests": _deletion_requests(seed_mod, random.Random(args.seed + 1), now, args.deletions),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fixture, separators=(",", ":")) + "\n")
    print(f"accepted {accepted}/{len(events)}, processed {len(rows)}; risk summary {summary}")
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()

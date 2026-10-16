#!/usr/bin/env python3
"""Export a JSON fixture for the static live demo by running the real pipeline.

Nothing in the fixture is invented in the browser. This script:

1. Builds synthetic events with the same generator as ``src/scripts/seed_demo.py``.
2. Sends them through the real FastAPI app (``POST /events`` then
   ``POST /process/drain``) using an in-process test client and a throwaway
   SQLite database in a temp directory, so no database file lands in the repo.
3. Includes synthetic data subject requests (access and deletion) as
   ``dsr_*`` events in the same stream. The pipeline stores them as requests
   (``src/app/dsr.py``), and ``GET /api/v1/dsr`` reports each one's
   per-regulation deadline and SLA status as of the export time.
4. Writes everything to ``demo/site/data/fixture.json``.

Usage:
    python demo/export_fixture.py [--events 360] [--dsr 64] [--seed 7] [--out demo/site/data/fixture.json]
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
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "demo" / "site" / "data" / "fixture.json"


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", type=int, default=360)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--dsr", type=int, default=64, help="number of data subject requests")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    logging.disable(logging.WARNING)
    _isolate_storage()
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    from src.app.dsr import AT_RISK_WINDOW_DAYS, DSR_EVENT_TYPES
    from src.app.main import app
    from src.app.regulations import ComplianceChecker, RegulationFramework

    seed_mod = _load_seed_module()
    rng = random.Random(args.seed)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    events = [seed_mod.make_event(rng, i, now) for i in range(args.events)]
    events += seed_mod.risky_patterns(args.events, now)
    dsr_events = seed_mod.dsr_events(random.Random(args.seed + 1), args.dsr, now)
    events += dsr_events

    with TestClient(app) as client:
        accepted = sum(client.post("/events", json=ev).status_code == 202 for ev in events)
        token = client.post("/token", data={"username": "admin", "password": "admin123"}).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        processed = client.post("/process/drain", headers=headers).json()
        summary = client.get("/compliance/summary", headers=headers).json()
        dsr = client.get(f"/api/v1/dsr?as_of={seed_mod.iso(now)}", headers=headers).json()
        deadlines = client.get("/api/v1/dsr/deadlines").json()["deadlines"]

    rows = []
    dsr_flags: dict[str, list[str]] = {}
    dsr_processed = 0
    for item in processed:
        ev, res = item["event"], item.get("result")
        if res is None:
            continue
        if ev["event_type"] in DSR_EVENT_TYPES:
            # Shown per request below, not as viewing events.
            dsr_processed += 1
            rid = (ev.get("extra_metadata") or {}).get("request_id")
            dsr_flags.setdefault(rid, []).extend(
                f
                for f in res["flags"]
                if f.startswith("dsr_") or f.endswith(("_access_violation", "_deletion_violation"))
            )
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
                "third_party": bool(extra.get("third_party")),
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

    requests_out = []
    for r in dsr["requests"]:
        binding = r["binding"] or {}
        requests_out.append(
            {
                "id": r["request_id"],
                "user_id": r["user_id"],
                "region": r["region"],
                "type": r["request_type"],
                "regulations": r["regulations"],
                "received": r["received_at"],
                "extension_noticed": r["extension_noticed_at"],
                "completed": r["completed_at"],
                "elapsed_days": r["elapsed_days"],
                "due": r["due"],
                "deadline_days": r["deadline_days"],
                "extended": r["extended"],
                "late_extension": r["late_extension"],
                "statutory": binding.get("statutory"),
                "citation": binding.get("citation"),
                "state": r["state"],
                "status": r["status"],
                "breached_regulations": r["breached_regulations"],
                "pipeline_flags": sorted(set(dsr_flags.get(r["request_id"], []))),
            }
        )

    regions_seen = sorted({r["region"] for r in rows})
    fixture = {
        "meta": {
            "generated_at": seed_mod.iso(now),
            "seed": args.seed,
            "events_sent": len(events),
            "events_accepted": accepted,
            "events_processed": len(rows),
            "dsr_events_processed": dsr_processed,
            "risk_summary": summary,
            "dsr_summary": dsr["summary"],
            "at_risk_window_days": AT_RISK_WINDOW_DAYS,
            "source": "src/scripts/seed_demo.py generator -> POST /events -> POST /process/drain -> GET /api/v1/dsr",
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
            "dsr_deadlines": deadlines,
            "regions_seen": regions_seen,
        },
        "events": rows,
        "data_subject_requests": requests_out,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fixture, separators=(",", ":")) + "\n")
    print(
        f"accepted {accepted}/{len(events)}, processed {len(rows)} viewing events and "
        f"{dsr_processed} DSR events; risk summary {summary}; DSR {dsr['summary']['by_status']}"
    )
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()

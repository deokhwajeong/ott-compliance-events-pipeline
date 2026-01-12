from .queue import drain
from .compliance_rules import evaluate_compliance
from .db import SessionLocal
from .models import ProcessedEvent
from datetime import datetime
import json

def process_events():
    """Process all events in queue and save results to DB."""
    db = SessionLocal()
    try:
        events = drain()
        results = []
        for e in events:
            try:
                result = evaluate_compliance(e, db)
                
                # Save to DB
                db_processed = ProcessedEvent(
                    event_id=e["event_id"],
                    risk_score=result["score"],
                    risk_level=result["risk_level"],
                    flags=json.dumps(result["flags"]),
                    processed_at=datetime.utcnow()
                )
                db.add(db_processed)
                
                results.append({
                    "content_id": e["content_id"],
                    "risk": result["risk_level"]
                })
            except Exception as ex:
                print(f"Error processing event {e.get('event_id')}: {ex}")
        db.commit()
        return results
    finally:
        db.close()

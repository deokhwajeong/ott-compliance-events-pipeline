from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from .schemas import Event
from .queue import enqueue_event, dequeue_event, drain, stats_snapshot, mark_processed, mark_error
from .compliance_rules import evaluate_compliance
from .db import get_db, engine
from .models import Base, RawEvent, ProcessedEvent, AggregateStats
from .auth import authenticate_user, create_access_token, get_current_active_user, Token, User, fake_users_db, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="OTT Compliance Events Pipeline")
# In-memory list to store results of processed events (for quick access, but also stored in DB)
_RESULTS = []

# Mount static files and templates for UI
app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
templates = Jinja2Templates(directory="src/app/templates")

@app.get("/", response_class=HTMLResponse)
async def ui(request: Request):
    """Serve the dashboard user interface."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api")
async def root():
    """Health-check endpoint."""
    return {"message": "OTT Compliance Events Pipeline"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT token."""
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: Event, db: Session = Depends(get_db)):
    """Receive an event and place it on the queue."""
    # Save to DB
    db_event = RawEvent(
        event_id=event.event_id,
        user_id=event.user_id,
        device_id=event.device_id,
        content_id=event.content_id,
        event_type=event.event_type,
        timestamp=datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')),
        region=event.region,
        is_eu=event.is_eu,
        has_consent=event.has_consent,
        ip_address=event.ip_address,
        error_code=event.error_code,
        extra_metadata=json.dumps(event.extra_metadata) if event.extra_metadata else None,
        subscription_plan=event.subscription_plan
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    enqueue_event(event.model_dump())
    return {"status": "queued"}

@app.post("/process/one")
async def process_one(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Process a single event from the queue and return the result."""
    ev = dequeue_event()
    if ev is None:
        return {"status": "empty_queue"}
    try:
        result = evaluate_compliance(ev, db)
        _RESULTS.append({"event": ev, "result": result})
        
        # Save processed event to DB
        db_processed = ProcessedEvent(
            event_id=ev["event_id"],
            risk_score=result["score"],
            risk_level=result["risk_level"],
            flags=json.dumps(result["flags"]),
            processed_at=datetime.utcnow()
        )
        db.add(db_processed)
        db.commit()
        
        mark_processed()
        return {"status": "processed", "result": result}
    except Exception as e:
        mark_error()
        return {"status": "error", "error": str(e)}

@app.post("/process/drain")
async def process_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Process all events currently in the queue and return their results."""
    events = drain()
    results = []
    for ev in events:
        try:
            result = evaluate_compliance(ev, db)
            _RESULTS.append({"event": ev, "result": result})
            
            # Save to DB
            db_processed = ProcessedEvent(
                event_id=ev["event_id"],
                risk_score=result["score"],
                risk_level=result["risk_level"],
                flags=json.dumps(result["flags"]),
                processed_at=datetime.utcnow()
            )
            db.add(db_processed)
            
            mark_processed()
            results.append({"event": ev, "result": result})
        except Exception as e:
            mark_error()
            results.append({"event": ev, "error": str(e)})
    db.commit()
    return results

@app.get("/stats/summary")
async def stats_summary(current_user: User = Depends(get_current_active_user)):
    """Return a snapshot of processing statistics and queue size."""
    return stats_snapshot()

@app.get("/results/latest")
async def results_latest(limit: int = 5, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Return the most recently processed results up to the provided limit."""
    processed = db.query(ProcessedEvent).order_by(ProcessedEvent.processed_at.desc()).limit(limit).all()
    results = []
    for p in processed:
        # Get original event from RawEvent
        raw_event = db.query(RawEvent).filter(RawEvent.event_id == p.event_id).first()
        if raw_event:
            results.append({
                "event": {
                    "event_id": raw_event.event_id,
                    "user_id": raw_event.user_id,
                    "content_id": raw_event.content_id,
                    "region": raw_event.region,
                    "event_type": raw_event.event_type
                },
                "result": {
                    "score": p.risk_score,
                    "risk_level": p.risk_level,
                    "flags": json.loads(p.flags)
                }
            })
    return results

@app.get("/compliance/summary")
async def compliance_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Return a summary of risk levels for processed events."""
    from sqlalchemy import func
    counts = db.query(
        ProcessedEvent.risk_level,
        func.count(ProcessedEvent.id).label('count')
    ).group_by(ProcessedEvent.risk_level).all()
    
    summary = {"low": 0, "medium": 0, "high": 0}
    total = 0
    for level, count in counts:
        summary[level] = count
        total += count
    summary["total_processed"] = total
    return summary

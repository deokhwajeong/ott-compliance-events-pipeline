from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from .metrics import MetricsRecorder
from .audit_log import audit_logger, AuditAction, ActorRole
from .report_generator import report_generator
import logging

logger = logging.getLogger(__name__)

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
    
    # 메트릭 기록
    MetricsRecorder.record_event(event.event_type, event.user_id)
    
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


# ========================
# Prometheus 메트릭 엔드포인트
# ========================

@app.get("/metrics")
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    return StreamingResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ========================
# 감시 로그 엔드포인트
# ========================

@app.post("/api/v1/audit/log")
async def log_audit(
    action: str,
    actor_id: str,
    target_user_id: str = None,
    details: dict = None,
    current_user: User = Depends(get_current_active_user)
):
    """감시 로그 기록"""
    try:
        audit_log = audit_logger.log(
            action=AuditAction[action.upper()],
            actor_id=actor_id,
            actor_role=ActorRole.ADMIN,
            target_user_id=target_user_id,
            details=details
        )
        return {
            "status": "logged",
            "log_id": audit_log.timestamp,
            "action": audit_log.action
        }
    except Exception as e:
        logger.error(f"감시 로그 기록 실패: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/audit/data-access")
async def log_data_access(
    target_user_id: str,
    resource: str,
    current_user: User = Depends(get_current_active_user)
):
    """데이터 접근 로그"""
    audit_logger.log_data_access(
        actor_id=current_user.username,
        target_user_id=target_user_id,
        resource=resource
    )
    return {"status": "logged", "action": "data_access"}


@app.post("/api/v1/audit/data-export")
async def log_data_export(
    target_user_id: str,
    export_format: str = "json",
    current_user: User = Depends(get_current_active_user)
):
    """데이터 내보내기 로그"""
    audit_logger.log_data_export(
        actor_id=current_user.username,
        target_user_id=target_user_id,
        export_format=export_format
    )
    return {"status": "logged", "action": "data_export"}


@app.post("/api/v1/audit/data-delete")
async def log_data_delete(
    target_user_id: str,
    reason: str,
    current_user: User = Depends(get_current_active_user)
):
    """데이터 삭제 로그"""
    audit_logger.log_data_delete(
        actor_id=current_user.username,
        target_user_id=target_user_id,
        reason=reason
    )
    return {"status": "logged", "action": "data_delete"}


# ========================
# 규정 준수 리포트 엔드포인트
# ========================

@app.get("/api/v1/reports/daily")
async def get_daily_report(current_user: User = Depends(get_current_active_user)):
    """일일 규정 준수 리포트"""
    report = report_generator.generate_daily_report()
    return report.to_dict()


@app.get("/api/v1/reports/daily/html")
async def get_daily_report_html(current_user: User = Depends(get_current_active_user)):
    """일일 규정 준수 리포트 (HTML)"""
    report = report_generator.generate_daily_report()
    return HTMLResponse(content=report.to_html())


@app.get("/api/v1/reports/weekly")
async def get_weekly_report(current_user: User = Depends(get_current_active_user)):
    """주간 규정 준수 리포트"""
    report = report_generator.generate_weekly_report()
    return report.to_dict()


@app.get("/api/v1/reports/weekly/html")
async def get_weekly_report_html(current_user: User = Depends(get_current_active_user)):
    """주간 규정 준수 리포트 (HTML)"""
    report = report_generator.generate_weekly_report()
    return HTMLResponse(content=report.to_html())


@app.get("/api/v1/reports/monthly")
async def get_monthly_report(current_user: User = Depends(get_current_active_user)):
    """월간 규정 준수 리포트"""
    report = report_generator.generate_monthly_report()
    return report.to_dict()


@app.get("/api/v1/reports/monthly/html")
async def get_monthly_report_html(current_user: User = Depends(get_current_active_user)):
    """월간 규정 준수 리포트 (HTML)"""
    report = report_generator.generate_monthly_report()
    return HTMLResponse(content=report.to_html())

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
# New ML and compliance modules
from .geoip_validator import geoip_validator
from .ml_models import anomaly_detector, violation_predictor
from .alerting import alerting_system
from .adaptive_thresholds import adaptive_thresholds
from .cache import cache_manager
from .user_segments import user_segmentation
from .network_analysis import network_fraud_detector
from .model_scheduler import model_scheduler
from .regulations import compliance_checker, RegulationFramework
from .roi_calculator import roi_calculator
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


# ========================
# Startup and Shutdown Events
# ========================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    logger.info("Starting up OTT Compliance Events Pipeline...")
    
    # Start the model retraining scheduler
    try:
        model_scheduler.start()
        logger.info("Model retraining scheduler started successfully")
    except Exception as e:
        logger.warning(f"Could not start model scheduler: {e}")
    
    # Verify Redis connection
    try:
        if hasattr(cache_manager, 'is_connected'):
            status = "connected" if cache_manager.is_connected else "disconnected"
            logger.info(f"Redis cache: {status}")
    except Exception as e:
        logger.warning(f"Could not verify cache connection: {e}")
    
    logger.info("Startup complete - all services initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down OTT Compliance Events Pipeline...")
    
    # Stop the scheduler
    try:
        model_scheduler.stop()
        logger.info("Model retraining scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")
    
    # Save all models
    try:
        anomaly_detector.save_model()
        adaptive_thresholds.save_model()
        user_segmentation.save_model()
        network_fraud_detector.save_model()
        logger.info("All models saved successfully")
    except Exception as e:
        logger.warning(f"Error saving models: {e}")
    
    logger.info("Shutdown complete")

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
    
    # Record metrics
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
# Prometheus Metrics Endpoint
# ========================

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return StreamingResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ========================
# Audit Log Endpoints
# ========================

@app.post("/api/v1/audit/log")
async def log_audit(
    action: str,
    actor_id: str,
    target_user_id: str = None,
    details: dict = None,
    current_user: User = Depends(get_current_active_user)
):
    """Record audit log"""
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
        logger.error(f"Failed to record audit log: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/audit/data-access")
async def log_data_access(
    target_user_id: str,
    resource: str,
    current_user: User = Depends(get_current_active_user)
):
    """Log data access"""
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
    """Log data export"""
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
    """Log data deletion"""
    audit_logger.log_data_delete(
        actor_id=current_user.username,
        target_user_id=target_user_id,
        reason=reason
    )
    return {"status": "logged", "action": "data_delete"}


# ========================
# Compliance Report Endpoints
# ========================

@app.get("/api/v1/reports/daily")
async def get_daily_report(current_user: User = Depends(get_current_active_user)):
    """Daily compliance report"""
    report = report_generator.generate_daily_report()
    return report.to_dict()


@app.get("/api/v1/reports/daily/html")
async def get_daily_report_html(current_user: User = Depends(get_current_active_user)):
    """Daily compliance report (HTML)"""
    report = report_generator.generate_daily_report()
    return HTMLResponse(content=report.to_html())


@app.get("/api/v1/reports/weekly")
async def get_weekly_report(current_user: User = Depends(get_current_active_user)):
    """Weekly compliance report"""
    report = report_generator.generate_weekly_report()
    return report.to_dict()


@app.get("/api/v1/reports/weekly/html")
async def get_weekly_report_html(current_user: User = Depends(get_current_active_user)):
    """Weekly compliance report (HTML)"""
    report = report_generator.generate_weekly_report()
    return HTMLResponse(content=report.to_html())


@app.get("/api/v1/reports/monthly")
async def get_monthly_report(current_user: User = Depends(get_current_active_user)):
    """Monthly compliance report"""
    report = report_generator.generate_monthly_report()
    return report.to_dict()


@app.get("/api/v1/reports/monthly/html")
async def get_monthly_report_html(current_user: User = Depends(get_current_active_user)):
    """Monthly compliance report (HTML)"""
    report = report_generator.generate_monthly_report()
    return HTMLResponse(content=report.to_html())

# ========================
# ML Models and Advanced Analysis Endpoints
# ========================

@app.get("/api/v1/ml/status")
async def ml_status(current_user: User = Depends(get_current_active_user)):
    """Get status of all ML models"""
    return {
        "anomaly_detector": {
            "model_type": "ensemble",
            "algorithms": ["isolation_forest", "local_outlier_factor"],
            "feature_history_size": len(anomaly_detector.feature_history),
            "is_trained": anomaly_detector.isolation_forest is not None,
        },
        "violation_predictor": {
            "model_type": "pattern_based",
            "prediction_factors": 4,
            "pattern_history_size": len(violation_predictor.patterns),
        },
        "adaptive_thresholds": {
            "current_base_threshold": 8.0,
            "time_zones_tracked": len(adaptive_thresholds.time_stats),
            "regions_tracked": len(adaptive_thresholds.region_stats),
        },
    }


@app.post("/api/v1/ml/predict/violation")
async def predict_violations(
    user_id: str,
    recent_events: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Predict potential compliance violations for a user"""
    # Get recent user activity
    recent = db.query(ProcessedEvent).filter(
        ProcessedEvent.event_id.in_(
            db.query(RawEvent.event_id).filter(
                RawEvent.user_id == user_id
            ).order_by(RawEvent.timestamp.desc()).limit(recent_events).all()
        )
    ).all()
    
    if not recent:
        return {"user_id": user_id, "violation_likelihood": 0.0, "risk_factors": []}
    
    # Calculate average risk
    avg_risk = sum(e.risk_score for e in recent) / len(recent) if recent else 0.0
    
    # Get violation prediction
    prediction = violation_predictor.predict_violation_likelihood(
        user_id=user_id,
        recent_events_count=len(recent),
        average_risk_score=avg_risk
    )
    
    return prediction


@app.post("/api/v1/ml/retrain/{model_name}")
async def trigger_model_retraining(
    model_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """Trigger immediate retraining of a specific model"""
    result = model_scheduler.trigger_immediate_retraining(model_name)
    return result


@app.get("/api/v1/ml/scheduler/status")
async def get_scheduler_status(current_user: User = Depends(get_current_active_user)):
    """Get model retraining scheduler status"""
    return model_scheduler.get_scheduler_status()


# ========================
# GeoIP and Network Analysis Endpoints
# ========================

@app.post("/api/v1/geoip/validate")
async def validate_geoip(
    user_id: str,
    ip_address: str,
    claimed_region: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Validate IP address against claimed region"""
    result = geoip_validator.validate_ip_region_consistency(ip_address, claimed_region)
    
    # Check for impossible travel
    impossible_travel = geoip_validator.detect_impossible_travel(
        user_id=user_id,
        current_ip=ip_address
    )
    
    result["impossible_travel"] = impossible_travel
    return result


@app.get("/api/v1/network/fraud-rings")
async def get_fraud_rings(
    min_ring_size: int = 5,
    current_user: User = Depends(get_current_active_user)
):
    """Detect and list fraud rings"""
    rings = network_fraud_detector.detect_fraud_rings(min_ring_size=min_ring_size)
    stats = network_fraud_detector.get_network_statistics()
    
    return {
        "detected_rings": rings,
        "network_statistics": stats,
    }


@app.post("/api/v1/network/user-risk")
async def get_network_user_risk(
    user_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get user's network-based fraud risk"""
    risk = network_fraud_detector.get_user_network_risk(user_id, max_hops=2)
    
    return {
        "user_id": user_id,
        "network_risk_score": risk["risk_score"],
        "risk_factors": risk["risk_factors"],
        "connected_suspicious_users": risk["connected_suspicious_users"],
    }


# ========================
# Cache Management Endpoints
# ========================

@app.get("/api/v1/cache/stats")
async def get_cache_stats(current_user: User = Depends(get_current_active_user)):
    """Get cache statistics"""
    try:
        if hasattr(cache_manager, 'get_stats'):
            stats = cache_manager.get_stats()
            return {
                "cache_type": "redis",
                "statistics": stats,
            }
        else:
            return {
                "cache_type": "in-memory",
                "statistics": {"status": "fallback_cache_active"},
            }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/cache/clear")
async def clear_cache(
    pattern: str = "*",
    current_user: User = Depends(get_current_active_user)
):
    """Clear cache entries matching pattern"""
    try:
        cache_manager.clear_pattern(pattern)
        return {"status": "cleared", "pattern": pattern}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================
# User Segmentation Endpoints
# ========================

@app.get("/api/v1/users/segment/{user_id}")
async def get_user_segment(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user segment classification"""
    # Get user activity statistics
    all_events = db.query(RawEvent).filter(RawEvent.user_id == user_id).all()
    
    if not all_events:
        return {"user_id": user_id, "segment": "new_user", "segment_confidence": 0.5}
    
    # Calculate metrics
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    events_30d = [e for e in all_events if e.timestamp >= thirty_days_ago]
    events_7d = [e for e in all_events if e.timestamp >= seven_days_ago]
    
    violations_30d = db.query(ProcessedEvent).filter(
        ProcessedEvent.event_id.in_([e.event_id for e in events_30d]),
        ProcessedEvent.risk_level.in_(["high", "critical"])
    ).count()
    
    days_since_signup = max(1, (now - min(e.timestamp for e in all_events)).days)
    last_activity_days = (now - max(e.timestamp for e in all_events)).days
    avg_risk = sum(
        db.query(ProcessedEvent.risk_score).filter(
            ProcessedEvent.event_id == e.event_id
        ).scalar() or 0.0 for e in events_30d
    ) / len(events_30d) if events_30d else 0.0
    
    segment = user_segmentation.update_user_profile(
        user_id=user_id,
        event_count_30d=len(events_30d),
        event_count_7d=len(events_7d),
        violation_count_30d=violations_30d,
        days_since_signup=days_since_signup,
        last_activity_days_ago=last_activity_days,
        avg_risk_score=avg_risk
    )
    
    # Get risk parameters for segment
    params = user_segmentation.get_segment_risk_parameters(segment)
    
    return {
        "user_id": user_id,
        "segment": segment.value,
        "metrics": {
            "events_30d": len(events_30d),
            "events_7d": len(events_7d),
            "violations_30d": violations_30d,
            "days_since_signup": days_since_signup,
            "last_activity_days_ago": last_activity_days,
            "average_risk_score": avg_risk,
        },
        "risk_parameters": params,
    }


@app.get("/api/v1/users/segments/statistics")
async def get_segment_statistics(current_user: User = Depends(get_current_active_user)):
    """Get distribution of user segments"""
    stats = user_segmentation.get_segment_statistics()
    return stats


# ========================
# Compliance and Regulations Endpoints
# ========================

@app.get("/api/v1/regulations/supported")
async def get_supported_regulations():
    """Get list of supported regulations"""
    from regulations import Regulation
    
    return {
        "regulations": [r.value for r in Regulation],
        "total": len(Regulation),
    }


@app.post("/api/v1/compliance/check")
async def check_compliance(
    user_id: str,
    event_type: str,
    region: str,
    current_user: User = Depends(get_current_active_user)
):
    """Check event compliance against multi-country regulations"""
    details = {"has_explicit_consent": True}  # Default
    
    result = compliance_checker.evaluate_event_compliance(
        user_id=user_id,
        event_type=event_type,
        region=region,
        event_details=details
    )
    
    return result


@app.get("/api/v1/compliance/roi")
async def get_compliance_roi(
    time_period_months: int = 12,
    total_users: int = 100000,
    current_user: User = Depends(get_current_active_user)
):
    """Generate compliance system ROI report"""
    # Get metrics from database
    db_local = next(get_db())
    
    violations_detected = db_local.query(ProcessedEvent).filter(
        ProcessedEvent.risk_level.in_(["high", "critical"])
    ).count()
    
    # Estimate prevented violations (assume 80% prevention rate with good detection)
    violations_prevented = int(violations_detected * 0.8)
    
    # Estimate incidents prevented
    incidents_prevented = max(1, int(violations_prevented / 100))
    
    applicable_regulations = ["GDPR", "CCPA", "PIPL", "PDPA"]
    
    report = roi_calculator.generate_roi_report(
        violations_detected=violations_detected,
        violations_prevented=violations_prevented,
        incidents_prevented=incidents_prevented,
        total_users=total_users,
        customer_lifetime_value=500,
        time_period_months=time_period_months,
        applicable_regulations=applicable_regulations
    )
    
    return report


# ========================
# Alerting System Endpoints
# ========================

@app.post("/api/v1/alerts/send")
async def send_alert(
    severity: str,
    title: str,
    message: str,
    current_user: User = Depends(get_current_active_user)
):
    """Send an alert through the alerting system"""
    import asyncio
    
    try:
        await alerting_system.send_alert(
            severity=severity,
            title=title,
            message=message,
            details={
                "triggered_by": current_user.username,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        return {"status": "sent", "severity": severity}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/alerts/recent")
async def get_recent_alerts(
    limit: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    """Get recent alerts sent by the system"""
    history = alerting_system.alert_history[-limit:]
    return {
        "alerts": history,
        "total": len(alerting_system.alert_history),
    }
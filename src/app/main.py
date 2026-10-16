import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from .adaptive_thresholds import adaptive_thresholds
from .alerting import alerting_system
from .audit_log import ActorRole, AuditAction, audit_logger
from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    fake_users_db,
    get_current_active_user,
)
from .cache import cache_manager
from .compliance_rules import evaluate_compliance
from .db import engine, get_db

# New ML and compliance modules
from .geoip_validator import geoip_validator
from .metrics import MetricsRecorder
from .ml_models import anomaly_detector, violation_predictor
from .model_scheduler import model_scheduler
from .models import Base, ProcessedEvent, RawEvent
from .network_analysis import network_fraud_detector
from .queue import dequeue_event, drain, enqueue_event, mark_error, mark_processed, stats_snapshot
from .regulations import RegulationFramework, compliance_checker
from .report_generator import report_generator
from .roi_calculator import roi_calculator
from .schemas import Event

# Security modules
from .security import DataSanitizer, SecurityValidator, rate_limiter
from .user_segments import user_segmentation

logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OTT Compliance Events Pipeline",
    version="0.2.0",
    description=(
        "Ingests OTT viewing, login and ad events, checks each one against the "
        "privacy rules of its market (GDPR, CCPA, PIPEDA, LGPD, ...), adds "
        "behavioral risk signals, and stores a scored result. "
        "Get a token from `POST /token` (local demo account `admin` / `admin123`)."
    ),
)
# In-memory list to store results of processed events (for quick access, but also stored in DB)
_RESULTS = []

# Templates for the dashboard UI (resolved relative to this file so the app
# starts from any working directory)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
        if hasattr(cache_manager, "is_connected"):
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
        anomaly_detector.save_models()
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
    return templates.TemplateResponse(request, "dashboard.html")


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
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: Event, request: Request, db: Session = Depends(get_db)):
    """Receive an event with comprehensive validation and rate limiting"""

    # Rate limiting check (per client address)
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    # Security validation
    event_dict = event.model_dump()
    is_valid, errors = SecurityValidator.validate_event_data(event_dict)
    if not is_valid:
        logger.warning(f"Security validation failed: {errors}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security validation failed: {', '.join(errors[:3])}",
        )

    # Sanitize event data
    event_dict = DataSanitizer.sanitize_event(event_dict)

    # Save to DB
    try:
        db_event = RawEvent(
            event_id=event_dict["event_id"],
            user_id=event_dict["user_id"],
            device_id=event_dict["device_id"],
            content_id=event_dict["content_id"],
            event_type=event_dict["event_type"],
            timestamp=datetime.fromisoformat(event_dict["timestamp"].replace("Z", "+00:00"))
            if event_dict["timestamp"]
            else datetime.utcnow(),
            region=event_dict["region"],
            is_eu=event_dict["is_eu"],
            has_consent=event_dict["has_consent"],
            ip_address=event_dict["ip_address"],
            error_code=event_dict.get("error_code"),
            extra_metadata=json.dumps(event_dict.get("extra_metadata", {}))
            if event_dict.get("extra_metadata")
            else None,
            subscription_plan=event_dict.get("subscription_plan"),
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to store event")

    # Record metrics
    MetricsRecorder.record_event(event_dict["event_type"], event_dict["user_id"])

    # Enqueue for processing
    try:
        enqueue_event(event_dict)
    except Exception as e:
        logger.error(f"Queue error: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue event")

    return {"status": "queued", "event_id": event_dict["event_id"]}


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
            processed_at=datetime.utcnow(),
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
                processed_at=datetime.utcnow(),
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
async def results_latest(
    limit: int = 5, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Return the most recently processed results up to the provided limit."""
    processed = db.query(ProcessedEvent).order_by(ProcessedEvent.processed_at.desc()).limit(limit).all()
    results = []
    for p in processed:
        # Get original event from RawEvent
        raw_event = db.query(RawEvent).filter(RawEvent.event_id == p.event_id).first()
        if raw_event:
            results.append(
                {
                    "event": {
                        "event_id": raw_event.event_id,
                        "user_id": raw_event.user_id,
                        "content_id": raw_event.content_id,
                        "region": raw_event.region,
                        "event_type": raw_event.event_type,
                    },
                    "result": {
                        "score": p.risk_score,
                        "risk_level": p.risk_level,
                        "flags": json.loads(p.flags),
                    },
                }
            )
    return results


@app.get("/compliance/summary")
async def compliance_summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Return a summary of risk levels for processed events."""
    from sqlalchemy import func

    counts = (
        db.query(ProcessedEvent.risk_level, func.count(ProcessedEvent.id).label("count"))
        .group_by(ProcessedEvent.risk_level)
        .all()
    )

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
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ========================
# Audit Log Endpoints
# ========================


@app.post("/api/v1/audit/log")
async def log_audit(
    action: str,
    actor_id: str,
    target_user_id: str = None,
    details: dict = None,
    current_user: User = Depends(get_current_active_user),
):
    """Record audit log"""
    try:
        audit_log = audit_logger.log(
            action=AuditAction[action.upper()],
            actor_id=actor_id,
            actor_role=ActorRole.ADMIN,
            target_user_id=target_user_id,
            details=details,
        )
        return {"status": "logged", "log_id": audit_log.timestamp, "action": audit_log.action}
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/audit/data-access")
async def log_data_access(
    target_user_id: str, resource: str, current_user: User = Depends(get_current_active_user)
):
    """Log data access"""
    audit_logger.log_data_access(
        actor_id=current_user.username, target_user_id=target_user_id, resource=resource
    )
    return {"status": "logged", "action": "data_access"}


@app.post("/api/v1/audit/data-export")
async def log_data_export(
    target_user_id: str, export_format: str = "json", current_user: User = Depends(get_current_active_user)
):
    """Log data export"""
    audit_logger.log_data_export(
        actor_id=current_user.username, target_user_id=target_user_id, export_format=export_format
    )
    return {"status": "logged", "action": "data_export"}


@app.post("/api/v1/audit/data-delete")
async def log_data_delete(
    target_user_id: str, reason: str, current_user: User = Depends(get_current_active_user)
):
    """Log data deletion"""
    audit_logger.log_data_delete(actor_id=current_user.username, target_user_id=target_user_id, reason=reason)
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
            "pattern_history_size": len(violation_predictor.violation_patterns),
        },
        "adaptive_thresholds": {
            "current_base_threshold": 8.0,
            "hours_tracked": len(adaptive_thresholds.time_of_day_stats),
            "regions_tracked": len(adaptive_thresholds.region_stats),
        },
    }


@app.post("/api/v1/ml/predict/violation")
async def predict_violations(
    user_id: str,
    recent_events: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Predict potential compliance violations for a user"""
    history = [
        _raw_event_to_dict(e)
        for e in db.query(RawEvent)
        .filter(RawEvent.user_id == user_id)
        .order_by(RawEvent.timestamp.desc())
        .limit(recent_events)
        .all()
    ]
    if not history:
        return {"user_id": user_id, "violation_likelihood": 0.0, "risk_factors": []}

    prediction = violation_predictor.predict_violation_likelihood(history, history[0])
    prediction["user_id"] = user_id
    return prediction


def _raw_event_to_dict(e: RawEvent) -> dict:
    return {
        "event_id": e.event_id,
        "event_type": e.event_type,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "region": e.region,
        "ip_address": e.ip_address,
        "is_eu": e.is_eu,
        "has_consent": e.has_consent,
        "error_code": e.error_code,
    }


@app.post("/api/v1/ml/retrain/{model_name}")
async def trigger_model_retraining(model_name: str, current_user: User = Depends(get_current_active_user)):
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
    current_user: User = Depends(get_current_active_user),
):
    """Validate IP address against claimed region"""
    result = geoip_validator.validate_ip_region_consistency(ip_address, claimed_region)

    # Check for impossible travel against the user's last known location
    impossible_travel = geoip_validator.check_user_travel(user_id, ip_address, datetime.utcnow().timestamp())

    result["impossible_travel"] = impossible_travel
    return result


@app.get("/api/v1/network/fraud-rings")
async def get_fraud_rings(min_ring_size: int = 5, current_user: User = Depends(get_current_active_user)):
    """Detect and list fraud rings"""
    rings = network_fraud_detector.detect_fraud_rings(min_ring_size=min_ring_size)
    stats = network_fraud_detector.get_network_statistics()

    return {
        "detected_rings": rings,
        "network_statistics": stats,
    }


@app.post("/api/v1/network/user-risk")
async def get_network_user_risk(user_id: str, current_user: User = Depends(get_current_active_user)):
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
        if hasattr(cache_manager, "get_stats"):
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
async def clear_cache(pattern: str = "*", current_user: User = Depends(get_current_active_user)):
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
    user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
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

    violations_30d = (
        db.query(ProcessedEvent)
        .filter(
            ProcessedEvent.event_id.in_([e.event_id for e in events_30d]),
            ProcessedEvent.risk_level.in_(["high", "critical"]),
        )
        .count()
    )

    days_since_signup = max(1, (now - min(e.timestamp for e in all_events)).days)
    last_activity_days = (now - max(e.timestamp for e in all_events)).days
    avg_risk = (
        sum(
            db.query(ProcessedEvent.risk_score).filter(ProcessedEvent.event_id == e.event_id).scalar() or 0.0
            for e in events_30d
        )
        / len(events_30d)
        if events_30d
        else 0.0
    )

    segment = user_segmentation.update_user_profile(
        user_id=user_id,
        event_count_30d=len(events_30d),
        event_count_7d=len(events_7d),
        violation_count_30d=violations_30d,
        days_since_signup=days_since_signup,
        last_activity_days_ago=last_activity_days,
        avg_risk_score=avg_risk,
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
    from .regulations import Regulation

    return {
        "regulations": [r.value for r in Regulation],
        "total": len(Regulation),
    }


@app.post("/api/v1/compliance/check")
async def check_compliance(
    user_id: str, event_type: str, region: str, current_user: User = Depends(get_current_active_user)
):
    """Check event compliance against multi-country regulations"""
    details = {"has_explicit_consent": True}  # Default

    result = compliance_checker.evaluate_event_compliance(
        user_id=user_id, event_type=event_type, region=region, event_details=details
    )

    return result


@app.get("/api/v1/compliance/roi")
async def get_compliance_roi(
    time_period_months: int = 12,
    total_users: int = 100000,
    current_user: User = Depends(get_current_active_user),
):
    """Generate compliance system ROI report"""
    # Get metrics from database
    db_local = next(get_db())

    violations_detected = (
        db_local.query(ProcessedEvent).filter(ProcessedEvent.risk_level.in_(["high", "critical"])).count()
    )

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
        applicable_regulations=applicable_regulations,
    )

    return report


# ========================
# Alerting System Endpoints
# ========================


@app.post("/api/v1/alerts/send")
async def send_alert(
    severity: str, title: str, message: str, current_user: User = Depends(get_current_active_user)
):
    """Send an alert through the alerting system"""
    from .alerting import AlertSeverity

    try:
        await alerting_system.send_alert(
            title=f"{title}: {message}",
            severity=AlertSeverity(severity.lower()),
            event={"user_id": current_user.username},
            flags=[],
            risk_score=0.0,
        )
        return {"status": "sent", "severity": severity}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/alerts/recent")
async def get_recent_alerts(limit: int = 10, current_user: User = Depends(get_current_active_user)):
    """Get recent alerts sent by the system"""
    history = alerting_system.alert_history[-limit:]
    return {
        "alerts": history,
        "total": len(alerting_system.alert_history),
    }


# ========================
# Advanced Analytics Endpoints
# ========================


@app.get("/api/v1/analytics/ml-models/status")
async def get_ml_models_status(current_user: User = Depends(get_current_active_user)):
    """Get status of all ML models"""
    from .ml_models import anomaly_detector, model_metrics, violation_predictor

    return {
        "anomaly_detector": {
            "feature_history_size": len(anomaly_detector.feature_history),
            "is_trained": anomaly_detector.isolation_forest is not None,
            "max_history": anomaly_detector.max_history,
        },
        "violation_predictor": {
            "pattern_count": len(violation_predictor.violation_patterns),
            "stats": violation_predictor.get_violation_stats(),
        },
        "metrics": model_metrics.get_metrics(),
    }


@app.get("/api/v1/analytics/cache/stats")
async def get_analytics_cache_stats(current_user: User = Depends(get_current_active_user)):
    """Get cache manager statistics"""
    return {
        "cache": cache_manager.get_stats(),
        "database_pool": database_pool_stats() if hasattr(engine, "pool") else {},
    }


def database_pool_stats():
    """Get database connection pool stats"""
    try:
        from .db import get_pool_stats

        return get_pool_stats()
    except Exception:
        return {}


@app.get("/api/v1/analytics/performance-metrics")
async def get_performance_metrics(current_user: User = Depends(get_current_active_user)):
    """Get application performance metrics"""
    from prometheus_client import generate_latest

    metrics = generate_latest().decode("utf-8")

    # Parse key metrics
    lines = [ln for ln in metrics.split("\n") if not ln.startswith("#") and ln.strip()]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_metrics": len(lines),
        "metrics_sample": lines[:20],
        "metrics_full": metrics if len(metrics) < 50000 else metrics[:50000] + "... (truncated)",
    }


@app.post("/api/v1/analytics/ml-models/retrain")
async def retrain_ml_models(force: bool = False, current_user: User = Depends(get_current_active_user)):
    """Manually trigger ML model retraining"""
    try:
        anomaly_result = anomaly_detector.retrain_models(force=force)

        return {
            "status": "retraining_initiated",
            "anomaly_detector": {
                "success": anomaly_result,
                "sample_size": len(anomaly_detector.feature_history),
            },
            "triggered_by": current_user.username,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Retraining error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/user-risk/{user_id}")
async def get_user_risk_profile(
    user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get comprehensive risk profile for a specific user"""
    try:
        # Get user segment
        segment = user_segmentation.get_user_segment(user_id).value

        # Get recent events
        recent_events = (
            db.query(RawEvent)
            .filter(RawEvent.user_id == user_id)
            .order_by(RawEvent.timestamp.desc())
            .limit(100)
            .all()
        )

        if not recent_events:
            return {"user_id": user_id, "error": "No events found", "segment": None}

        # Convert to dict
        events_dict = [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "region": e.region,
                "ip_address": e.ip_address,
                "is_eu": e.is_eu,
                "has_consent": e.has_consent,
                "error_code": e.error_code,
            }
            for e in recent_events
        ]

        # Predict violation likelihood
        violation_pred = violation_predictor.predict_violation_likelihood(
            events_dict, events_dict[0] if events_dict else {}
        )

        # Get anomaly score for recent event
        anomaly_result = anomaly_detector.ensemble_anomaly_detection(
            events_dict[0] if events_dict else {}, record=False
        )

        return {
            "user_id": user_id,
            "segment": segment,
            "risk_profile": {
                "violation_likelihood": violation_pred["violation_likelihood"],
                "violation_confidence": violation_pred["confidence"],
                "risk_factors": violation_pred["risk_factors"],
                "predicted_regulations": violation_pred["predicted_regulations"],
            },
            "anomaly_detection": {
                "is_anomaly": anomaly_result["is_anomaly"],
                "ensemble_score": anomaly_result["ensemble_score"],
                "flags": anomaly_result["flags"],
            },
            "recent_events_count": len(recent_events),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"User risk profile error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/compliance-trends")
async def get_compliance_trends(
    days: int = 7, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get compliance trends over time"""
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get processed events in date range
        events = db.query(ProcessedEvent).filter(ProcessedEvent.processed_at >= cutoff_date).all()

        if not events:
            return {
                "days": days,
                "events_count": 0,
                "trends": {"low_risk": [], "medium_risk": [], "high_risk": []},
            }

        # Aggregate by day
        daily_stats = {}
        for event in events:
            day = event.processed_at.date().isoformat()
            if day not in daily_stats:
                daily_stats[day] = {"low": 0, "medium": 0, "high": 0}

            risk_level = event.risk_level.lower()
            if risk_level in daily_stats[day]:
                daily_stats[day][risk_level] += 1

        return {
            "days": days,
            "events_count": len(events),
            "daily_stats": daily_stats,
            "risk_distribution": {
                "low": sum(1 for e in events if e.risk_level.lower() == "low"),
                "medium": sum(1 for e in events if e.risk_level.lower() == "medium"),
                "high": sum(1 for e in events if e.risk_level.lower() == "high"),
            },
        }
    except Exception as e:
        logger.error(f"Compliance trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/security/validation-status")
async def get_security_status(current_user: User = Depends(get_current_active_user)):
    """Get security validation status"""
    return {
        "security_validator": {
            "sql_injection_patterns": len(SecurityValidator.SQL_INJECTION_PATTERNS),
            "xss_patterns": len(SecurityValidator.XSS_PATTERNS),
            "path_traversal_patterns": len(SecurityValidator.PATH_TRAVERSAL_PATTERNS),
        },
        "rate_limiter": {
            "max_requests": rate_limiter.max_requests,
            "window_seconds": rate_limiter.window_seconds,
            "active_keys": len(rate_limiter.requests),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ========================
# Advanced Analytics & Reporting Endpoints
# ========================


@app.get("/api/v1/reports/executive-summary")
async def get_executive_summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get executive summary report"""
    from .advanced_analytics import ReportGenerator

    return ReportGenerator.generate_executive_summary(db)


@app.get("/api/v1/reports/compliance")
async def get_compliance_report(
    days: int = 7, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get detailed compliance report for specified period"""
    from .advanced_analytics import ReportGenerator

    return ReportGenerator.generate_compliance_report(db, days=days)


@app.get("/api/v1/analytics/geographic-distribution")
async def get_geographic_distribution(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get event distribution by region"""
    try:
        from .advanced_analytics import AdvancedAnalytics

        raw_events = db.query(RawEvent).all()

        events_dict = [
            {
                "region": e.region,
                "is_eu": e.is_eu,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in raw_events
        ]

        geo_dist = AdvancedAnalytics.get_geographic_distribution(events_dict)

        return {
            "geographic_distribution": geo_dist,
            "total_events": len(raw_events),
            "unique_regions": len(geo_dist),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Geographic distribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/ml-model-performance")
async def get_ml_performance(current_user: User = Depends(get_current_active_user)):
    """Get ML model performance metrics"""
    from .advanced_analytics import ReportGenerator
    from .ml_models import model_metrics

    return ReportGenerator.generate_ml_performance_report(model_metrics.get_metrics())


@app.get("/api/v1/analytics/risk-distribution")
async def get_risk_distribution(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get overall risk level distribution"""
    try:
        from .advanced_analytics import AdvancedAnalytics

        processed_events = db.query(ProcessedEvent).all()

        distribution = AdvancedAnalytics.get_risk_distribution(processed_events)
        total = sum(distribution.values())

        return {
            "risk_distribution": distribution,
            "total_events": total,
            "high_risk_percentage": round((distribution.get("high", 0) / total * 100) if total > 0 else 0, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Risk distribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/top-risk-factors")
async def get_top_risk_factors(
    limit: int = 10, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get most frequently detected risk factors"""
    try:
        import json

        from .advanced_analytics import AdvancedAnalytics

        processed_events = db.query(ProcessedEvent).limit(1000).all()

        events_dict = []
        for event in processed_events:
            try:
                flags = json.loads(event.flags) if isinstance(event.flags, str) else event.flags
            except Exception:
                flags = []

            events_dict.append({"flags": flags if isinstance(flags, list) else [flags]})

        risk_factors = AdvancedAnalytics.get_top_risk_factors(events_dict)

        return {"top_risk_factors": risk_factors[:limit], "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Top risk factors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# Dashboard data
# ========================


@app.get("/api/v1/dashboard/overview")
async def dashboard_overview(
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Everything the dashboard renders, computed from stored events."""
    from collections import Counter, defaultdict

    rows = (
        db.query(ProcessedEvent, RawEvent)
        .join(RawEvent, RawEvent.event_id == ProcessedEvent.event_id)
        .order_by(ProcessedEvent.processed_at.desc())
        .all()
    )

    risk = {"low": 0, "medium": 0, "high": 0}
    flag_counts: Counter = Counter()
    regions: dict = defaultdict(lambda: {"events": 0, "flagged": 0, "high": 0})
    regulation_violations: Counter = Counter()
    for processed, raw in rows:
        flags = json.loads(processed.flags or "[]")
        risk[processed.risk_level] = risk.get(processed.risk_level, 0) + 1
        flag_counts.update(flags)
        r = regions[raw.region]
        r["events"] += 1
        r["flagged"] += 1 if flags else 0
        r["high"] += 1 if processed.risk_level == "high" else 0
        for f in flags:
            parts = f.split("_")
            if f.endswith("_violation") and parts[0].upper() in {
                reg.value for reg in RegulationFramework.REGULATION_REQUIREMENTS
            }:
                regulation_violations[parts[0].upper()] += 1

    by_region = [
        {
            "region": code,
            "regulations": [reg.value for reg in RegulationFramework.get_regulations_for_region(code)],
            **counts,
        }
        for code, counts in sorted(regions.items(), key=lambda kv: -kv[1]["events"])
    ]

    latest = [
        {
            "event_id": raw.event_id,
            "user_id": raw.user_id,
            "event_type": raw.event_type,
            "region": raw.region,
            "content_id": raw.content_id,
            "risk_level": processed.risk_level,
            "score": processed.risk_score,
            "flags": json.loads(processed.flags or "[]"),
            "processed_at": processed.processed_at.isoformat() if processed.processed_at else None,
        }
        for processed, raw in rows[:limit]
    ]

    return {
        "total_processed": len(rows),
        "risk_distribution": risk,
        "queue": stats_snapshot(),
        "by_region": by_region,
        "regulation_violations": dict(regulation_violations.most_common()),
        "top_flags": [{"flag": f, "count": c} for f, c in flag_counts.most_common(8)],
        "latest": latest,
    }

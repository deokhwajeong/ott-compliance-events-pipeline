import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from .adaptive_thresholds import adaptive_thresholds
from .alerting import AlertSeverity, alerting_system
from .dsr import DSR_EVENT_TYPES, apply_dsr_event

# Import new ML modules
from .geoip_validator import geoip_validator
from .ml_models import anomaly_detector, violation_predictor
from .models import ProcessedEvent, RawEvent
from .network_analysis import network_fraud_detector
from .regulations import compliance_checker
from .user_segments import user_segmentation

logger = logging.getLogger(__name__)

# Keep references to fire-and-forget alert tasks so they are not GC'd early.
_background_tasks: set = set()


def _parse_timestamp(timestamp: Any) -> datetime:
    """Parse an ISO-8601 timestamp into a naive UTC datetime (DB convention)."""
    if isinstance(timestamp, str):
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(UTC).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
    return datetime.utcnow()


def evaluate_compliance(event: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
    """
    Enhanced compliance evaluation with ML, GeoIP validation, and multi-country rules.
    Integrates all new compliance modules into a comprehensive risk assessment.
    """
    flags = []
    score = 0.0
    detailed_findings = {}

    event_type = (event.get("event_type") or "").lower()
    region = event.get("region", "unknown")
    user_id = event.get("user_id")
    device_id = event.get("device_id")
    ip_address = event.get("ip_address")
    timestamp = event.get("timestamp")
    is_eu = event.get("is_eu", False)
    has_consent = event.get("has_consent", True)
    subscription_plan = event.get("subscription_plan", "basic")
    payment_method = event.get("payment_method")
    extra = event.get("extra_metadata") or {}
    event_time = _parse_timestamp(timestamp)

    # ========================
    # 1. GeoIP Validation
    # ========================
    if ip_address and region:
        try:
            geoip_result = geoip_validator.validate_ip_region_consistency(ip_address, region)
            geo_flags = [
                f
                for f in geoip_result.get("flags", [])
                if f in {"ip_region_mismatch", "vpn_detected", "datacenter_ip"}
            ]
            if geo_flags:
                flags.extend(geo_flags)
                score += geoip_result.get("score_adjustment", 0)
                detailed_findings["geoip_validation"] = geoip_result

            # Check for impossible travel against the user's last location
            if user_id:
                travel_result = geoip_validator.check_user_travel(user_id, ip_address, event_time.timestamp())
                if travel_result and travel_result.get("impossible_travel", False):
                    flags.append("impossible_travel_detected")
                    score += 3.0
                    detailed_findings["impossible_travel"] = travel_result
        except Exception as e:
            logger.warning(f"GeoIP validation failed: {e}")

    # ========================
    # 2. Missing Identifiers
    # ========================
    if not user_id:
        flags.append("missing_user_id")
        score += 2
    if not device_id:
        flags.append("missing_device_id")
        score += 2

    # ========================
    # 3. Basic Event Type Rules
    # ========================
    if event_type in {"error", "login_failed", "token_refresh_failed"}:
        flags.append("auth_or_playback_error")
        score += 3

    # ========================
    # 4. Consent and Privacy
    # ========================
    # A data subject request is the subscriber exercising a right, not
    # processing that needs consent, so the consent check does not apply.
    is_dsr = event_type in DSR_EVENT_TYPES
    if is_eu and not has_consent and not is_dsr:
        flags.append("eu_privacy_violation")
        score += 5

    # ========================
    # 5. User Segmentation
    # ========================
    user_segment = None
    user_risk_params = None
    if db and user_id:
        try:
            # Get user metrics
            all_events = db.query(RawEvent).filter(RawEvent.user_id == user_id).all()

            if all_events:
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
                        db.query(ProcessedEvent.risk_score)
                        .filter(ProcessedEvent.event_id == e.event_id)
                        .scalar()
                        or 0.0
                        for e in events_30d
                    )
                    / len(events_30d)
                    if events_30d
                    else 0.0
                )

                user_segment = user_segmentation.update_user_profile(
                    user_id=user_id,
                    event_count_30d=len(events_30d),
                    event_count_7d=len(events_7d),
                    violation_count_30d=violations_30d,
                    days_since_signup=days_since_signup,
                    last_activity_days_ago=last_activity_days,
                    avg_risk_score=avg_risk,
                )

                user_risk_params = user_segmentation.get_segment_risk_parameters(user_segment)
                detailed_findings["user_segment"] = {
                    "segment": user_segment.value,
                    "risk_parameters": user_risk_params,
                }
        except Exception as e:
            logger.warning(f"User segmentation failed: {e}")

    # ========================
    # 6. Adaptive Threshold Adjustment
    # ========================
    try:
        dynamic_threshold = adaptive_thresholds.get_dynamic_risk_threshold(
            user_segment=user_segment.value if user_segment else "normal_user",
            hour=event_time.hour,
            region=region,
        )
        detailed_findings["adaptive_threshold"] = dynamic_threshold
    except Exception as e:
        logger.warning(f"Adaptive threshold calculation failed: {e}")
        dynamic_threshold = 8.0

    # ========================
    # 7. Network Fraud Detection
    # ========================
    if user_id:
        try:
            network_fraud_detector.add_user_event(
                user_id=user_id, device_id=device_id, ip_address=ip_address, payment_method=payment_method
            )

            network_risk = network_fraud_detector.get_user_network_risk(user_id, max_hops=2)

            if network_risk.get("risk_score", 0) > 0.5:
                flags.append("fraud_ring_connection")
                score += network_risk["risk_score"] * 2.0

            detailed_findings["network_analysis"] = network_risk
        except Exception as e:
            logger.warning(f"Network fraud detection failed: {e}")

    # ========================
    # 8. Enhanced ML Anomaly Detection
    # ========================
    ml_result = None
    if db and user_id:
        try:
            # The detector extracts its own numeric features from the raw
            # event and adds them to its rolling history.
            ml_result = anomaly_detector.ensemble_anomaly_detection(event)

            if ml_result["is_anomaly"]:
                flags.append("ml_ensemble_anomaly")
                score += 2.0

            detailed_findings["ml_anomaly_detection"] = ml_result
        except Exception as e:
            logger.warning(f"ML anomaly detection failed: {e}")

    # ========================
    # 9. Violation Prediction
    # ========================
    if user_id:
        try:
            history = []
            if db:
                rows = (
                    db.query(RawEvent)
                    .filter(RawEvent.user_id == user_id)
                    .order_by(RawEvent.timestamp.desc())
                    .limit(100)
                    .all()
                )
                history = [
                    {
                        "event_type": r.event_type,
                        "is_eu": r.is_eu,
                        "has_consent": r.has_consent,
                        "ip_address": r.ip_address,
                    }
                    for r in reversed(rows)
                ]
            violation_pred = violation_predictor.predict_violation_likelihood(history or [event], event)

            if violation_pred.get("violation_likelihood", 0) > 0.7:
                flags.append("high_violation_risk")
                score += violation_pred.get("violation_likelihood", 0.7) * 2.0

            detailed_findings["violation_prediction"] = violation_pred
        except Exception as e:
            logger.warning(f"Violation prediction failed: {e}")

    # ========================
    # 10. Multi-Country Compliance Check
    # ========================
    try:
        compliance_result = compliance_checker.evaluate_event_compliance(
            user_id=user_id or "unknown",
            event_type=event_type,
            region=region,
            event_details={
                "has_explicit_consent": has_consent,
                "is_eu": is_eu,
                "gpc_signal": bool(extra.get("gpc")),
                "targeted_ad": bool(extra.get("targeted")),
                "third_party_share": bool(extra.get("third_party")),
            },
        )

        if not compliance_result["compliant"]:
            flags.append("multi_country_violation")
            for v in compliance_result["violations"]:
                flags.append(f"{v['regulation'].lower()}_{v['action']}_violation")
            # Same weight as the direct EU consent check: a confirmed statutory
            # violation should never land in the "low" bucket.
            score += len(compliance_result["violations"]) * 5.0

        detailed_findings["compliance_check"] = compliance_result
    except Exception as e:
        logger.warning(f"Compliance check failed: {e}")

    # ========================
    # 10b. Data Subject Requests
    # ========================
    # Receipt, extension and completion events update the request record in
    # dsr.py. A completion after the regulation's deadline is a statutory
    # finding and is weighted like any other confirmed violation.
    if is_dsr and db is not None:
        try:
            regs = detailed_findings.get("compliance_check", {}).get("applicable_regulations", [])
            dsr_result = apply_dsr_event(event, regs, db)
            flags.extend(dsr_result["flags"])
            missed = [f for f in dsr_result["flags"] if f.endswith("_violation")]
            if missed:
                flags.append("dsr_deadline_missed")
            score += len(missed) * 5.0
            if dsr_result["finding"]:
                detailed_findings["data_subject_request"] = dsr_result["finding"]
        except Exception as e:
            logger.warning(f"DSR tracking failed: {e}")

    # ========================
    # 11. Subscription-Based Adjustment
    # ========================
    if subscription_plan == "premium":
        score = max(0, score - 1)
    elif subscription_plan == "basic":
        score += 1

    # ========================
    # 12. Time-Window Analysis
    # ========================
    if db and user_id and timestamp:
        try:
            window_start = event_time - timedelta(hours=1)

            recent_events = (
                db.query(RawEvent)
                .filter(
                    RawEvent.user_id == user_id,
                    RawEvent.timestamp >= window_start,
                    RawEvent.timestamp <= event_time,
                )
                .all()
            )

            regions_in_window = set(e.region for e in recent_events)
            if len(regions_in_window) > 2:
                flags.append("multi_region_access")
                score += 2

            if len(recent_events) > 10:
                flags.append("high_frequency_activity")
                score += 1
        except Exception as e:
            logger.warning(f"Time-window analysis failed: {e}")

    # ========================
    # 13. Determine Risk Level
    # ========================
    # Use adaptive threshold if available
    threshold_high = dynamic_threshold if dynamic_threshold else 8.0
    threshold_medium = max(0, threshold_high - 3.0)

    if score >= threshold_high:
        risk_level = "high"
    elif score >= threshold_medium:
        risk_level = "medium"
    else:
        risk_level = "low"

    result = {
        "score": round(score, 2),
        "risk_level": risk_level,
        "flags": flags,
        "detailed_findings": detailed_findings,
    }

    # ========================
    # 14. Record Metrics and Trigger Alerts
    # ========================
    if db and risk_level in ["high", "critical"]:
        try:
            # Record for adaptive threshold learning
            adaptive_thresholds.record_event(
                risk_score=score,
                is_violation=risk_level == "high",
                user_segment=user_segment.value if user_segment else "normal_user",
                hour=event_time.hour,
                region=region,
            )

            # Send alert for high-risk events (fire-and-forget when an event
            # loop is running, e.g. inside the API; skipped in plain scripts)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                task = loop.create_task(
                    alerting_system.send_alert(
                        title=f"High-risk event detected for user {user_id}",
                        severity=AlertSeverity.HIGH,
                        event=event,
                        flags=flags,
                        risk_score=score,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
        except Exception as e:
            logger.warning(f"Failed to record metrics: {e}")

    return result

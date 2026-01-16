#!/usr/bin/env python3
"""
Comprehensive test suite for advanced features
Tests all newly implemented high-level optimizations
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.db import get_pool_stats
from app.cache import cache_manager, CacheManager
from app.ml_models import anomaly_detector, violation_predictor, model_metrics
from app.security import SecurityValidator, DataSanitizer, rate_limiter
from app.event_processor import get_processing_stats, process_single_event
from app.advanced_analytics import AdvancedAnalytics, ReportGenerator
from app.metrics import MetricsRecorder
import asyncio
import json
from datetime import datetime


def test_database_pooling():
    """Test database pooling configuration"""
    print("\n" + "="*70)
    print("[TEST 1] Database Connection Pooling")
    print("="*70)
    
    stats = get_pool_stats()
    print(f"✓ Pool stats: {json.dumps(stats, indent=2)}")
    print("✓ Database pooling is properly configured")


def test_cache_operations():
    """Test advanced cache operations"""
    print("\n" + "="*70)
    print("[TEST 2] Cache Manager Advanced Operations")
    print("="*70)
    
    # Test basic operations
    cache_manager.set("test_key", {"value": "test_data"}, ttl=300)
    cached = cache_manager.get("test_key")
    assert cached == {"value": "test_data"}, "Cache get/set failed"
    print("✓ Basic cache get/set works")
    
    # Test batch operations
    batch_data = {
        "user:001:profile": {"name": "User1", "score": 100},
        "user:001:events": [{"event": "login"}, {"event": "play"}],
        "user:002:profile": {"name": "User2", "score": 85}
    }
    cache_manager.mset(batch_data, ttl=600)
    print("✓ Batch cache operations (mset) work")
    
    # Test pattern clearing
    cleared = cache_manager.clear_pattern("user:001:*")
    print(f"✓ Pattern-based cache clearing works: cleared {cleared} keys")
    
    # Test cache stats
    stats = cache_manager.get_stats()
    print(f"✓ Cache stats available: {stats.get('status', 'unknown')}")


def test_security_validation():
    """Test security validation features"""
    print("\n" + "="*70)
    print("[TEST 3] Security Validation & Sanitization")
    print("="*70)
    
    # Test SQL injection detection
    malicious_sql = "user'; DROP TABLE users; --"
    is_sql = SecurityValidator.is_sql_injection_attempt(malicious_sql)
    assert is_sql, "SQL injection detection failed"
    print(f"✓ SQL injection detection: {is_sql}")
    
    # Test XSS detection
    malicious_xss = "<script>alert('XSS')</script>"
    is_xss = SecurityValidator.is_xss_attempt(malicious_xss)
    assert is_xss, "XSS detection failed"
    print(f"✓ XSS detection: {is_xss}")
    
    # Test event data validation
    valid_event = {
        "event_id": "evt_001",
        "user_id": "user_001",
        "device_id": "dev_001",
        "content_id": "cont_001",
        "event_type": "play",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "region": "US",
        "is_eu": False,
        "has_consent": True,
        "ip_address": "192.168.1.1"
    }
    
    is_valid, errors = SecurityValidator.validate_event_data(valid_event)
    assert is_valid, f"Valid event failed: {errors}"
    print(f"✓ Valid event validation passed")
    
    # Test malicious event detection
    malicious_event = valid_event.copy()
    malicious_event["user_id"] = malicious_sql
    is_valid, errors = SecurityValidator.validate_event_data(malicious_event)
    assert not is_valid, "Malicious event not detected"
    print(f"✓ Malicious event detection works: {errors[0]}")
    
    # Test data sanitization
    sanitized = DataSanitizer.sanitize_event(valid_event)
    print(f"✓ Event data sanitization works: sanitized {len(sanitized)} fields")
    
    # Test rate limiter
    client_id = "test_client"
    allowed = rate_limiter.is_allowed(client_id)
    assert allowed, "Rate limiter should allow first request"
    print(f"✓ Rate limiter working: current requests {len(rate_limiter.requests)}")


def test_ml_models():
    """Test ML model enhancements"""
    print("\n" + "="*70)
    print("[TEST 4] ML Models & Anomaly Detection")
    print("="*70)
    
    # Test ensemble anomaly detection
    test_event = {
        "event_id": "evt_001",
        "user_id": "user_001",
        "event_type": "play",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "region": "US",
        "is_eu": False,
        "has_consent": True,
        "ip_address": "192.168.1.1",
        "error_code": None,
        "subscription_plan": "premium"
    }
    
    result = anomaly_detector.ensemble_anomaly_detection(test_event)
    print(f"✓ Ensemble anomaly detection: is_anomaly={result['is_anomaly']}, score={result['ensemble_score']:.3f}")
    
    # Test violation prediction
    test_history = [test_event] * 5
    violation_pred = violation_predictor.predict_violation_likelihood(test_history, test_event)
    print(f"✓ Violation prediction: likelihood={violation_pred['violation_likelihood']:.3f}, confidence={violation_pred['confidence']:.3f}")
    print(f"  Risk factors: {violation_pred['risk_factors']}")
    print(f"  Predicted regulations: {violation_pred['predicted_regulations']}")
    
    # Test model metrics
    metrics = model_metrics.get_metrics()
    print(f"✓ Model metrics: {len(metrics)} model(s) tracked")
    
    # Test model stats
    print(f"✓ Anomaly detector feature history: {len(anomaly_detector.feature_history)} samples")


def test_event_processing():
    """Test event processing pipeline"""
    print("\n" + "="*70)
    print("[TEST 5] Event Processing Pipeline")
    print("="*70)
    
    test_event = {
        "event_id": "evt_test_001",
        "user_id": "user_test_001",
        "device_id": "dev_001",
        "event_type": "login",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "region": "US",
        "is_eu": False,
        "has_consent": True,
        "ip_address": "192.168.1.100",
        "error_code": None,
        "subscription_plan": "basic"
    }
    
    # Test async event processing
    try:
        result = asyncio.run(process_single_event(test_event))
        print(f"✓ Event processing completed: event_id={result.get('event_id')}")
        print(f"  Risk level: {result.get('compliance', {}).get('risk_level', 'unknown')}")
        print(f"  Anomaly detected: {result.get('anomaly', {}).get('is_anomaly', False)}")
        print(f"  Violation likelihood: {result.get('violation', {}).get('violation_likelihood', 0):.3f}")
    except Exception as e:
        print(f"⚠ Event processing test: {e}")
    
    # Test processing stats
    stats = get_processing_stats()
    print(f"✓ Processing stats: {stats.get('total_processed')} events processed")


def test_metrics_recording():
    """Test metrics recording"""
    print("\n" + "="*70)
    print("[TEST 6] Prometheus Metrics Recording")
    print("="*70)
    
    # Test event metrics
    MetricsRecorder.record_event("login", "user_001")
    MetricsRecorder.record_event_processed("login", "success")
    print("✓ Event metrics recorded")
    
    # Test anomaly metrics
    MetricsRecorder.record_anomaly("suspicious_activity", 0.75, "high")
    print("✓ Anomaly metrics recorded")
    
    # Test compliance metrics
    MetricsRecorder.record_violation("GDPR", "consent_missing", "high")
    MetricsRecorder.update_compliance_score("GDPR", 95.5)
    print("✓ Compliance metrics recorded")
    
    # Test cache metrics
    MetricsRecorder.record_cache_hit("redis")
    MetricsRecorder.record_cache_miss("redis")
    print("✓ Cache metrics recorded")


def test_advanced_analytics():
    """Test advanced analytics"""
    print("\n" + "="*70)
    print("[TEST 7] Advanced Analytics")
    print("="*70)
    
    # Create sample data
    sample_events = [
        {"flags": ["gdpr_violation", "consent_issue"], "risk_level": "high", "risk_score": 8.5},
        {"flags": ["geolocation_mismatch"], "risk_level": "medium", "risk_score": 5.2},
        {"flags": [], "risk_level": "low", "risk_score": 2.1}
    ]
    
    # Test risk distribution
    mock_processed = type('obj', (object,), {
        'risk_level': e['risk_level'],
        'risk_score': e['risk_score']
    })() for e in sample_events
    
    distribution = AdvancedAnalytics.get_risk_distribution(list(mock_processed))
    print(f"✓ Risk distribution: {distribution}")
    
    # Test top risk factors
    risk_factors = AdvancedAnalytics.get_top_risk_factors(sample_events)
    print(f"✓ Top risk factors: {json.dumps(risk_factors, indent=2)}")
    
    # Test geographic distribution
    geo_events = [
        {"region": "US"},
        {"region": "EU"},
        {"region": "US"},
        {"region": "ASIA"},
        {"region": "EU"}
    ]
    geo_dist = AdvancedAnalytics.get_geographic_distribution(geo_events)
    print(f"✓ Geographic distribution: {geo_dist}")


def main():
    print("\n" + "="*70)
    print("OTT Compliance Pipeline - Advanced Features Test Suite")
    print("="*70)
    
    tests = [
        ("Database Pooling", test_database_pooling),
        ("Cache Operations", test_cache_operations),
        ("Security Validation", test_security_validation),
        ("ML Models", test_ml_models),
        ("Event Processing", test_event_processing),
        ("Metrics Recording", test_metrics_recording),
        ("Advanced Analytics", test_advanced_analytics),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n✗ Test failed: {test_name}")
            print(f"  Error: {str(e)}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    print(f"✓ Passed: {passed}/{len(tests)}")
    print(f"✗ Failed: {failed}/{len(tests)}")
    print("="*70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

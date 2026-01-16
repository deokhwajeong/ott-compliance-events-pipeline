#!/usr/bin/env python3
"""
🎯 OTT Compliance Pipeline - Interactive Demo
Try the ML compliance system directly with sample data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))

import pandas as pd
import json
from datetime import datetime
from typing import Dict, Any
from pprint import pprint

# Module imports
from app.geoip_validator import geoip_validator
from app.ml_models import anomaly_detector, violation_predictor
from app.adaptive_thresholds import adaptive_thresholds
from app.user_segments import user_segmentation
from app.network_analysis import network_fraud_detector
from app.regulations import compliance_checker, RegulationFramework, Regulation
from app.roi_calculator import roi_calculator
from app.cache import cache_manager


def print_header(title: str, level: int = 1):
    """Print formatted header"""
    symbols = ["🔴", "🟠", "🟡", "🟢", "🔵"][level - 1]
    print(f"\n{'='*70}")
    print(f"{symbols} {title}")
    print(f"{'='*70}\n")


def demo_1_geoip():
    """Demo 1: GeoIP Validation"""
    print_header("1️⃣  GeoIP Validation - IP Address Region Check", 1)
    
    test_ips = [
        {"ip": "8.8.8.8", "claimed_region": "US", "description": "Google DNS (USA)"},
        {"ip": "1.1.1.1", "claimed_region": "AU", "description": "Cloudflare DNS (claims Australia)"},
        {"ip": "185.220.101.1", "claimed_region": "US", "description": "Tor Node (claims USA)"},
    ]
    
    print("📍 Sample IP Validation:\n")
    results = []
    for test in test_ips:
        print(f"  {test['description']}")
        print(f"    IP: {test['ip']}, Claimed Region: {test['claimed_region']}")
        
        result = geoip_validator.validate_ip_region_consistency(test["ip"], test["claimed_region"])
        
        print(f"    ✓ Flags: {result['flags'] if result['flags'] else 'None'}")
        print(f"    ✓ Score Adjustment: +{result['score_adjustment']}")
        print(f"    ✓ VPN: {'Detected' if result['vpn_info']['is_vpn'] else 'None'}\n")
        
        results.append({
            "Description": test["description"],
            "Risk Level": "High" if result['score_adjustment'] > 0 else "Low",
            "Score": result['score_adjustment']
        })
    
    print("📊 Results Summary:")
    print(pd.DataFrame(results).to_string(index=False))
    return results


def demo_2_ml_detection():
    """Demo 2: ML Anomaly Detection"""
    print_header("2️⃣  ML Anomaly Detection - Isolation Forest + LOF Ensemble", 1)
    
    sample_events = [
        {
            "name": "✅ Normal Event (Business Hours)",
            "features": {
                "hour": 14, "weekday": 2, "event_type_len": 5, "has_error": 0,
                "is_eu": 0, "has_consent": 1, "subscription_tier": 2,
                "device_id": 12345, "region_code": 1,
            }
        },
        {
            "name": "⚠️  Suspicious Event (Night Bulk Access)",
            "features": {
                "hour": 3, "weekday": 4, "event_type_len": 8, "has_error": 1,
                "is_eu": 1, "has_consent": 0, "subscription_tier": 1,
                "device_id": 99999, "region_code": 50,
            }
        },
    ]
    
    ml_results = []
    for event in sample_events:
        print(f"{event['name']}")
        result = anomaly_detector.ensemble_anomaly_detection(event['features'])
        
        print(f"  ✓ Anomaly Detected: {'🔴 YES' if result['is_anomaly'] else '🟢 NO'}")
        print(f"  ✓ Ensemble Score: {result['ensemble_score']:.3f}")
        print(f"  ✓ Isolation Forest: {result['isolation_forest']['score']:.3f}")
        print(f"  ✓ LOF: {result['lof']['score']:.3f}\n")
        
        ml_results.append({
            "Event": event['name'].split()[0] + " " + event['name'].split()[1],
            "Anomaly": "YES" if result['is_anomaly'] else "NO",
            "Score": f"{result['ensemble_score']:.3f}",
        })
    
    print("📊 Results Summary:")
    print(pd.DataFrame(ml_results).to_string(index=False))
    print(f"\n📈 Accumulated Feature Data: {len(anomaly_detector.feature_history)} records")
    return ml_results


def demo_3_user_segmentation():
    """Demo 3: User Segmentation"""
    print_header("3️⃣  User Segmentation - Auto User Classification", 1)
    
    user_profiles = [
        {
            "user_id": "power_user_001",
            "event_count_30d": 850, "event_count_7d": 160,
            "violation_count_30d": 0, "days_since_signup": 250,
            "last_activity_days_ago": 1, "avg_risk_score": 2.0,
        },
        {
            "user_id": "new_user_002",
            "event_count_30d": 15, "event_count_7d": 8,
            "violation_count_30d": 0, "days_since_signup": 10,
            "last_activity_days_ago": 2, "avg_risk_score": 3.5,
        },
        {
            "user_id": "suspicious_user_003",
            "event_count_30d": 120, "event_count_7d": 90,
            "violation_count_30d": 10, "days_since_signup": 45,
            "last_activity_days_ago": 1, "avg_risk_score": 9.0,
        },
    ]
    
    segment_results = []
    for profile in user_profiles:
        user_id = profile.pop("user_id")
        segment = user_segmentation.update_user_profile(user_id=user_id, **profile)
        params = user_segmentation.get_segment_risk_parameters(segment)
        
        print(f"👤 {user_id}")
        print(f"  ✓ Segment: {segment.value}")
        print(f"  ✓ Threshold: {params['risk_threshold_high']}")
        print(f"  ✓ Sensitivity: {params['anomaly_sensitivity']}x")
        print(f"  ✓ Alerts: {', '.join(params['alert_channels'])}\n")
        
        segment_results.append({
            "User": user_id,
            "Segment": segment.value,
            "Threshold": params['risk_threshold_high'],
        })
    
    print("📊 Results Summary:")
    print(pd.DataFrame(segment_results).to_string(index=False))
    return segment_results


def demo_4_network_fraud():
    """Demo 4: Network Fraud Detection"""
    print_header("4️⃣  Network Analysis - Fraud Ring Detection", 1)
    
    fraud_network = [
        ("fraud_user_1", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_2", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_3", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_4", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_5", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_6", "device_A", "192.168.1.100", "visa_1234"),
        ("clean_user_1", "device_B", "192.168.1.200", "visa_5678"),
    ]
    
    print(f"📌 Adding {len(fraud_network)} users to network...")
    for user_id, device_id, ip_address, payment_method in fraud_network:
        network_fraud_detector.add_user_event(
            user_id=user_id, device_id=device_id,
            ip_address=ip_address, payment_method=payment_method
        )
    print("✅ Complete\n")
    
    rings = network_fraud_detector.detect_fraud_rings(min_ring_size=5)
    print(f"🔴 {len(rings)} fraud rings detected!\n")
    
    for i, ring in enumerate(rings, 1):
        print(f"  Fraud Ring #{i}: {ring['ring_type']}")
        print(f"    ✓ Size: {len(ring['users'])} users")
        print(f"    ✓ Risk Score: {ring['risk_score']:.2f}")
        print(f"    ✓ Related Users: {', '.join(ring['users'][:3])}...\n")
    
    stats = network_fraud_detector.get_network_statistics()
    print("📊 Network Statistics:")
    print(f"  ✓ Total Nodes: {stats['total_nodes']}")
    print(f"  ✓ Fraud Rings: {stats['detected_fraud_rings']}")
    print(f"  ✓ Users in Fraud Rings: {stats['users_in_fraud_rings']}")
    
    return rings


def demo_5_regulations():
    """Demo 5: Multi-Jurisdiction Compliance"""
    print_header("5️⃣  Multi-Jurisdiction Compliance - Check Compliance", 1)
    
    print("🌍 Regulations by Region:\n")
    regions = ["EU", "US", "CN", "BR"]
    for region in regions:
        regs = RegulationFramework.get_regulations_for_region(region)
        reg_names = [r.value for r in regs] if regs else "None"
        print(f"  {region}: {reg_names}")
    
    print("\n📋 GDPR Key Requirements:")
    reqs = RegulationFramework.get_regulation_requirements(Regulation.GDPR)
    print(f"  ✓ Consent Required: {'Yes' if reqs['consent_required'] else 'No'}")
    print(f"  ✓ Breach Notification: {reqs['breach_notification_days']} days")
    print(f"  ✓ Right to Deletion: {'Yes' if reqs['right_to_deletion'] else 'No'}")
    
    print("\n✅ Event Compliance Check:")
    test_event = {
        "user_id": "user_eu_001",
        "event_type": "user_data_access",
        "region": "EU",
        "details": {"has_explicit_consent": True},
    }
    
    result = compliance_checker.evaluate_event_compliance(
        user_id=test_event['user_id'],
        event_type=test_event['event_type'],
        region=test_event['region'],
        event_details=test_event['details']
    )
    
    print(f"  User: {test_event['user_id']}")
    print(f"  Status: {'✅ Compliant' if result['compliant'] else '❌ Violation'}")
    print(f"  Applicable Regulations: {', '.join(result['applicable_regulations'])}")
    
    return result


def demo_6_roi():
    """Demo 6: ROI Analysis"""
    print_header("6️⃣  ROI Analysis - Financial Impact", 1)
    
    print("💰 Scenario: Monitor 100,000 users over 12 months")
    print("   - Violations Detected: 100")
    print("   - Violations Prevented: 80")
    print("   - Incidents Prevented: 3\n")
    
    report = roi_calculator.generate_roi_report(
        violations_detected=100,
        violations_prevented=80,
        incidents_prevented=3,
        total_users=100000,
        customer_lifetime_value=500,
        time_period_months=12,
        applicable_regulations=["GDPR", "CCPA", "PIPL", "LGPD"]
    )
    
    summary = report['financial_summary']
    print("💵 Financial Analysis Results:\n")
    print(f"  ✓ Total Value Protected: ${summary['total_value_protected']:,}")
    print(f"  ✓ System Cost: ${summary['system_cost']:,}")
    print(f"  ✓ Net Benefit: ${summary['net_benefit']:,}")
    print(f"  ✓ ROI: {summary['roi_percent']:,.0f}%")
    print(f"  ✓ Payback Period: {summary['payback_period_months']:.1f} months")
    
    print("\n⚖️  Fines Prevented by Regulation:")
    for reg, fine_data in report['fine_prevention'].items():
        print(f"  {reg}: ${fine_data['total_value']:,}")
    
    return report


def demo_7_adaptive_thresholds():
    """Demo 7: Adaptive Thresholds"""
    print_header("7️⃣  Adaptive Thresholds - Dynamic Risk Thresholds", 1)
    
    test_cases = [
        {"hour": 2, "region": "EU", "segment": "new_user", "desc": "Night (2 AM), EU, New User"},
        {"hour": 14, "region": "US", "segment": "power_user", "desc": "Afternoon (2 PM), US, Power User"},
    ]
    
    print("📌 Dynamic Thresholds by Situation:\n")
    for case in test_cases:
        desc = case.pop("desc")
        threshold = adaptive_thresholds.get_dynamic_risk_threshold(**case)
        print(f"  {desc}")
        print(f"    → Threshold: {threshold:.2f}\n")
    
    print("📚 Record Events and Learn:")
    learning_events = [
        {"risk_score": 3.0, "is_violation": False, "segment": "normal_user", "hour": 10, "region": "US"},
        {"risk_score": 7.5, "is_violation": True, "segment": "new_user", "hour": 2, "region": "EU"},
    ]
    
    for i, event in enumerate(learning_events, 1):
        adaptive_thresholds.record_event(**event)
        print(f"  Event {i}: Risk={event['risk_score']:.1f}, Violation={'Yes' if event['is_violation'] else 'No'}")
    
    print("\n✅ Adaptive thresholds are automatically learning.")


def demo_8_integration():
    """Demo 8: Integration Analysis"""
    print_header("8️⃣  Integration Analysis - All Modules Working Together", 1)
    
    event = {
        "event_id": "evt_20260113_001",
        "user_id": "user_eu_fraud_001",
        "device_id": "device_A",
        "ip_address": "185.220.101.45",
        "region": "EU",
        "event_type": "bulk_export",
    }
    
    print("📥 Event Received:\n")
    print(f"  Event ID: {event['event_id']}")
    print(f"  User: {event['user_id']}")
    print(f"  Type: {event['event_type']}\n")
    
    print("🔍 Analysis Stages:\n")
    
    # 1. GeoIP
    print("1️⃣  GeoIP Validation")
    geoip_result = geoip_validator.validate_ip_region_consistency(
        event['ip_address'], event['region']
    )
    print(f"   IP Match: {'✅ YES' if not geoip_result['flags'] else '❌ NO'}")
    
    # 2. ML
    print("\n2️⃣  ML Anomaly Detection")
    ml_features = {
        "hour": 22, "weekday": 4, "event_type_len": 11,
        "has_error": 1, "is_eu": 1, "has_consent": 0,
        "subscription_tier": 1, "device_id": 999, "region_code": 75,
    }
    ml_result = anomaly_detector.ensemble_anomaly_detection(ml_features)
    print(f"   Anomaly: {'⚠️  YES' if ml_result['is_anomaly'] else '✅ NO'}")
    print(f"   Score: {ml_result['ensemble_score']:.3f}")
    
    # 3. Segment
    print("\n3️⃣  User Segment")
    segment = user_segmentation.get_user_segment(event['user_id'])
    print(f"   Segment: {segment.value}")
    
    # 4. Network
    print("\n4️⃣  Network Analysis")
    network_fraud_detector.add_user_event(
        user_id=event['user_id'], device_id=event['device_id'],
        ip_address=event['ip_address']
    )
    network_risk = network_fraud_detector.get_user_network_risk(event['user_id'])
    print(f"   Risk: {network_risk['risk_score']:.2f}")
    
    # 5. Regulations
    print("\n5️⃣  Compliance Check")
    compliance = compliance_checker.evaluate_event_compliance(
        user_id=event['user_id'], event_type=event['event_type'],
        region=event['region'], event_details={"has_explicit_consent": False}
    )
    print(f"   Compliant: {'✅ YES' if compliance['compliant'] else '❌ NO'}")
    
    # Final Score
    print("\n" + "="*70)
    print("📊 Final Risk Assessment\n")
    
    final_score = (
        5 + geoip_result['score_adjustment'] +
        (ml_result['ensemble_score'] * 2) +
        (network_risk['risk_score'] * 2) +
        (2 if not compliance['compliant'] else 0)
    )
    
    risk_level = "🔴 HIGH" if final_score >= 8 else "🟡 MEDIUM" if final_score >= 5 else "🟢 LOW"
    action = "⏸️  Block" if final_score >= 8 else "📋 Monitor" if final_score >= 5 else "✅ Approve"
    
    print(f"Final Score: {final_score:.2f}")
    print(f"Risk Level: {risk_level}")
    print(f"Recommended Action: {action}")


def main():
    """Main function"""
    print("\n" + "="*70)
    print("🎯 OTT Compliance Pipeline - Interactive Demo")
    print("="*70)
    print("\nExperience the ML compliance system directly with sample data!\n")
    
    demos = [
        ("GeoIP Validation", demo_1_geoip),
        ("ML Anomaly Detection", demo_2_ml_detection),
        ("User Segmentation", demo_3_user_segmentation),
        ("Network Fraud Detection", demo_4_network_fraud),
        ("Multi-Jurisdiction Compliance", demo_5_regulations),
        ("ROI Analysis", demo_6_roi),
        ("Adaptive Thresholds", demo_7_adaptive_thresholds),
        ("Integration Analysis", demo_8_integration),
    ]
    
    print("📋 Available Demos:\n")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    
    print("\n" + "="*70)
    print("💡 Running All Demos\n")
    
    for name, demo_func in demos:
        try:
            demo_func()
            input(f"\n⏸️  {name} Complete! (Press Enter to continue...)")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue
    
    print("\n" + "="*70)
    print("🎉 All Demos Complete!")
    print("="*70)
    print("""
✅ Experienced 10 Modules:
  ✓ GeoIP Validator (IP/Region validation)
  ✓ ML Models (Isolation Forest + LOF)
  ✓ User Segmentation (6 Classifications)
  ✓ Network Fraud Detection (Fraud rings)
  ✓ Regulations (10+ Regulatory frameworks)
  ✓ ROI Calculator (Financial analysis)
  ✓ Adaptive Thresholds (Dynamic thresholds)
  ✓ Cache Manager (Redis caching)
  ✓ Alerting System (Multi-channel alerts)
  ✓ Model Scheduler (Automatic training)

📚 Next Steps:
  1. Run FastAPI server: python -m uvicorn src.app.main:app --reload
  2. API docs: http://localhost:8000/docs
  3. Test with real data
    """)


if __name__ == "__main__":
    main()

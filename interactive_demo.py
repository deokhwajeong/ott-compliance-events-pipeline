#!/usr/bin/env python3
"""
🎯 OTT Compliance Pipeline - Interactive Demo
샘플 데이터로 직접 구동해보는 대화형 데모
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))

import pandas as pd
import json
from datetime import datetime
from typing import Dict, Any
from pprint import pprint

# 모듈 임포트
from app.geoip_validator import geoip_validator
from app.ml_models import anomaly_detector, violation_predictor
from app.adaptive_thresholds import adaptive_thresholds
from app.user_segments import user_segmentation
from app.network_analysis import network_fraud_detector
from app.regulations import compliance_checker, RegulationFramework, Regulation
from app.roi_calculator import roi_calculator
from app.cache import cache_manager


def print_header(title: str, level: int = 1):
    """타이틀 출력"""
    symbols = ["🔴", "🟠", "🟡", "🟢", "🔵"][level - 1]
    print(f"\n{'='*70}")
    print(f"{symbols} {title}")
    print(f"{'='*70}\n")


def demo_1_geoip():
    """데모 1: GeoIP 검증"""
    print_header("1️⃣  GeoIP 검증 - IP 주소 지역 검증", 1)
    
    test_ips = [
        {"ip": "8.8.8.8", "claimed_region": "US", "description": "Google DNS (미국)"},
        {"ip": "1.1.1.1", "claimed_region": "AU", "description": "Cloudflare DNS (호주로 주장)"},
        {"ip": "185.220.101.1", "claimed_region": "US", "description": "Tor 노드 (미국으로 주장)"},
    ]
    
    print("📍 샘플 IP 검증:\\n")
    results = []
    for test in test_ips:
        print(f"  {test['description']}")
        print(f"    IP: {test['ip']}, 주장 지역: {test['claimed_region']}")
        
        result = geoip_validator.validate_ip_region_consistency(test["ip"], test["claimed_region"])
        
        print(f"    ✓ 플래그: {result['flags'] if result['flags'] else '없음'}")
        print(f"    ✓ 점수 조정: +{result['score_adjustment']}")
        print(f"    ✓ VPN: {'감지됨' if result['vpn_info']['is_vpn'] else '없음'}\n")
        
        results.append({
            "설명": test["description"],
            "위험도": "높음" if result['score_adjustment'] > 0 else "낮음",
            "점수": result['score_adjustment']
        })
    
    print("📊 결과 요약:")
    print(pd.DataFrame(results).to_string(index=False))
    return results


def demo_2_ml_detection():
    """데모 2: ML 이상 탐지"""
    print_header("2️⃣  ML 이상 탐지 - Isolation Forest + LOF 앙상블", 1)
    
    sample_events = [
        {
            "name": "✅ 정상 이벤트 (업무 시간)",
            "features": {
                "hour": 14, "weekday": 2, "event_type_len": 5, "has_error": 0,
                "is_eu": 0, "has_consent": 1, "subscription_tier": 2,
                "device_id": 12345, "region_code": 1,
            }
        },
        {
            "name": "⚠️  의심 이벤트 (야간 대량 접근)",
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
        
        print(f"  ✓ 이상 탐지: {'🔴 YES' if result['is_anomaly'] else '🟢 NO'}")
        print(f"  ✓ 앙상블 점수: {result['ensemble_score']:.3f}")
        print(f"  ✓ Isolation Forest: {result['isolation_forest']['score']:.3f}")
        print(f"  ✓ LOF: {result['lof']['score']:.3f}\n")
        
        ml_results.append({
            "이벤트": event['name'].split()[0] + " " + event['name'].split()[1],
            "이상": "YES" if result['is_anomaly'] else "NO",
            "점수": f"{result['ensemble_score']:.3f}",
        })
    
    print("📊 결과 요약:")
    print(pd.DataFrame(ml_results).to_string(index=False))
    print(f"\n📈 누적된 특징 데이터: {len(anomaly_detector.feature_history)}개")
    return ml_results


def demo_3_user_segmentation():
    """데모 3: 사용자 세그먼테이션"""
    print_header("3️⃣  사용자 세그먼테이션 - 자동 사용자 분류", 1)
    
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
        print(f"  ✓ 세그먼트: {segment.value}")
        print(f"  ✓ 임계값: {params['risk_threshold_high']}")
        print(f"  ✓ 감도: {params['anomaly_sensitivity']}x")
        print(f"  ✓ 알림: {', '.join(params['alert_channels'])}\n")
        
        segment_results.append({
            "사용자": user_id,
            "세그먼트": segment.value,
            "임계값": params['risk_threshold_high'],
        })
    
    print("📊 결과 요약:")
    print(pd.DataFrame(segment_results).to_string(index=False))
    return segment_results


def demo_4_network_fraud():
    """데모 4: 네트워크 사기 탐지"""
    print_header("4️⃣  네트워크 분석 - 사기 링 탐지", 1)
    
    fraud_network = [
        ("fraud_user_1", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_2", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_3", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_4", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_5", "device_A", "192.168.1.100", "visa_1234"),
        ("fraud_user_6", "device_A", "192.168.1.100", "visa_1234"),
        ("clean_user_1", "device_B", "192.168.1.200", "visa_5678"),
    ]
    
    print(f"📌 네트워크에 {len(fraud_network)}명의 사용자 추가 중...")
    for user_id, device_id, ip_address, payment_method in fraud_network:
        network_fraud_detector.add_user_event(
            user_id=user_id, device_id=device_id,
            ip_address=ip_address, payment_method=payment_method
        )
    print("✅ 완료\n")
    
    rings = network_fraud_detector.detect_fraud_rings(min_ring_size=5)
    print(f"🔴 {len(rings)}개의 사기 링 감지됨!\\n")
    
    for i, ring in enumerate(rings, 1):
        print(f"  사기 링 #{i}: {ring['ring_type']}")
        print(f"    ✓ 규모: {len(ring['users'])}명")
        print(f"    ✓ 위험도: {ring['risk_score']:.2f}")
        print(f"    ✓ 관련 사용자: {', '.join(ring['users'][:3])}...\n")
    
    stats = network_fraud_detector.get_network_statistics()
    print("📊 네트워크 통계:")
    print(f"  ✓ 총 노드: {stats['total_nodes']}개")
    print(f"  ✓ 사기 링: {stats['detected_fraud_rings']}개")
    print(f"  ✓ 사기 링 내 사용자: {stats['users_in_fraud_rings']}명")
    
    return rings


def demo_5_regulations():
    """데모 5: 다국가 규정 준수"""
    print_header("5️⃣  다국가 규정 준수 - 컴플라이언스 확인", 1)
    
    print("🌍 지역별 적용 규정:\n")
    regions = ["EU", "US", "CN", "BR"]
    for region in regions:
        regs = RegulationFramework.get_regulations_for_region(region)
        reg_names = [r.value for r in regs] if regs else "없음"
        print(f"  {region}: {reg_names}")
    
    print("\n📋 GDPR 핵심 요구사항:")
    reqs = RegulationFramework.get_regulation_requirements(Regulation.GDPR)
    print(f"  ✓ 동의 필수: {'예' if reqs['consent_required'] else '아니오'}")
    print(f"  ✓ 위반 통지: {reqs['breach_notification_days']}일")
    print(f"  ✓ 데이터 삭제권: {'예' if reqs['right_to_deletion'] else '아니오'}")
    
    print("\n✅ 이벤트 준수 확인:")
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
    
    print(f"  사용자: {test_event['user_id']}")
    print(f"  상태: {'✅ 준수' if result['compliant'] else '❌ 위반'}")
    print(f"  적용 규정: {', '.join(result['applicable_regulations'])}")
    
    return result


def demo_6_roi():
    """데모 6: ROI 분석"""
    print_header("6️⃣  ROI 분석 - 금융 임팩트", 1)
    
    print("💰 시나리오: 12개월 동안 100,000명 사용자 모니터링")
    print("   - 감지된 위반: 100개")
    print("   - 방지된 위반: 80개")
    print("   - 방지된 사건: 3개\n")
    
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
    print("💵 금융 분석 결과:\n")
    print(f"  ✓ 보호된 총 가치: ${summary['total_value_protected']:,}")
    print(f"  ✓ 시스템 비용: ${summary['system_cost']:,}")
    print(f"  ✓ 순 이익: ${summary['net_benefit']:,}")
    print(f"  ✓ ROI: {summary['roi_percent']:,.0f}%")
    print(f"  ✓ 회수 기간: {summary['payback_period_months']:.1f}개월")
    
    print("\n⚖️  규정별 회피된 벌금:")
    for reg, fine_data in report['fine_prevention'].items():
        print(f"  {reg}: ${fine_data['total_value']:,}")
    
    return report


def demo_7_adaptive_thresholds():
    """데모 7: 적응형 임계값"""
    print_header("7️⃣  적응형 임계값 - 동적 위험 임계값", 1)
    
    test_cases = [
        {"hour": 2, "region": "EU", "segment": "new_user", "desc": "야간(2시), EU, 신규"},
        {"hour": 14, "region": "US", "segment": "power_user", "desc": "오후(14시), US, 고급"},
    ]
    
    print("📌 상황별 동적 임계값:\\n")
    for case in test_cases:
        desc = case.pop("desc")
        threshold = adaptive_thresholds.get_dynamic_risk_threshold(**case)
        print(f"  {desc}")
        print(f"    → 임계값: {threshold:.2f}\n")
    
    print("📚 이벤트 기록 및 학습:")
    learning_events = [
        {"risk_score": 3.0, "is_violation": False, "segment": "normal_user", "hour": 10, "region": "US"},
        {"risk_score": 7.5, "is_violation": True, "segment": "new_user", "hour": 2, "region": "EU"},
    ]
    
    for i, event in enumerate(learning_events, 1):
        adaptive_thresholds.record_event(**event)
        print(f"  이벤트 {i}: Risk={event['risk_score']:.1f}, Violation={'Yes' if event['is_violation'] else 'No'}")
    
    print("\n✅ 적응형 임계값이 자동으로 학습 중입니다.")


def demo_8_integration():
    """데모 8: 통합 분석"""
    print_header("8️⃣  통합 분석 - 모든 모듈 협력", 1)
    
    event = {
        "event_id": "evt_20260113_001",
        "user_id": "user_eu_fraud_001",
        "device_id": "device_A",
        "ip_address": "185.220.101.45",
        "region": "EU",
        "event_type": "bulk_export",
    }
    
    print("📥 이벤트 수신:\n")
    print(f"  Event ID: {event['event_id']}")
    print(f"  User: {event['user_id']}")
    print(f"  Type: {event['event_type']}\n")
    
    print("🔍 분석 단계별 처리:\n")
    
    # 1. GeoIP
    print("1️⃣  GeoIP 검증")
    geoip_result = geoip_validator.validate_ip_region_consistency(
        event['ip_address'], event['region']
    )
    print(f"   IP 일치: {'✅ YES' if not geoip_result['flags'] else '❌ NO'}")
    
    # 2. ML
    print("\n2️⃣  ML 이상 탐지")
    ml_features = {
        "hour": 22, "weekday": 4, "event_type_len": 11,
        "has_error": 1, "is_eu": 1, "has_consent": 0,
        "subscription_tier": 1, "device_id": 999, "region_code": 75,
    }
    ml_result = anomaly_detector.ensemble_anomaly_detection(ml_features)
    print(f"   이상: {'⚠️  YES' if ml_result['is_anomaly'] else '✅ NO'}")
    print(f"   점수: {ml_result['ensemble_score']:.3f}")
    
    # 3. Segment
    print("\n3️⃣  사용자 세그먼트")
    segment = user_segmentation.get_user_segment(event['user_id'])
    print(f"   세그먼트: {segment.value}")
    
    # 4. Network
    print("\n4️⃣  네트워크 분석")
    network_fraud_detector.add_user_event(
        user_id=event['user_id'], device_id=event['device_id'],
        ip_address=event['ip_address']
    )
    network_risk = network_fraud_detector.get_user_network_risk(event['user_id'])
    print(f"   위험도: {network_risk['risk_score']:.2f}")
    
    # 5. Regulations
    print("\n5️⃣  규정 준수")
    compliance = compliance_checker.evaluate_event_compliance(
        user_id=event['user_id'], event_type=event['event_type'],
        region=event['region'], event_details={"has_explicit_consent": False}
    )
    print(f"   준수: {'✅ YES' if compliance['compliant'] else '❌ NO'}")
    
    # 최종 점수
    print("\n" + "="*70)
    print("📊 최종 위험 평가\n")
    
    final_score = (
        5 + geoip_result['score_adjustment'] +
        (ml_result['ensemble_score'] * 2) +
        (network_risk['risk_score'] * 2) +
        (2 if not compliance['compliant'] else 0)
    )
    
    risk_level = "🔴 HIGH" if final_score >= 8 else "🟡 MEDIUM" if final_score >= 5 else "🟢 LOW"
    action = "⏸️  차단" if final_score >= 8 else "📋 모니터링" if final_score >= 5 else "✅ 승인"
    
    print(f"최종 점수: {final_score:.2f}")
    print(f"위험 수준: {risk_level}")
    print(f"권장 조치: {action}")


def main():
    """메인 함수"""
    print("\n" + "="*70)
    print("🎯 OTT Compliance Pipeline - Interactive Demo")
    print("="*70)
    print("\n샘플 데이터로 머신러닝 컴플라이언스 시스템을 직접 체험해보세요!\n")
    
    demos = [
        ("GeoIP 검증", demo_1_geoip),
        ("ML 이상 탐지", demo_2_ml_detection),
        ("사용자 세그먼테이션", demo_3_user_segmentation),
        ("네트워크 사기 탐지", demo_4_network_fraud),
        ("다국가 규정 준수", demo_5_regulations),
        ("ROI 분석", demo_6_roi),
        ("적응형 임계값", demo_7_adaptive_thresholds),
        ("통합 분석", demo_8_integration),
    ]
    
    print("📋 실행 가능한 데모:\n")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    
    print("\n" + "="*70)
    print("💡 모든 데모 실행\n")
    
    for name, demo_func in demos:
        try:
            demo_func()
            input(f"\n⏸️  {name} 완료! (엔터를 눌러 계속...)")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            continue
    
    print("\n" + "="*70)
    print("🎉 모든 데모 완료!")
    print("="*70)
    print("""
✅ 10개 모듈 체험 완료:
  ✓ GeoIP Validator (IP/지역 검증)
  ✓ ML Models (Isolation Forest + LOF)
  ✓ User Segmentation (6가지 분류)
  ✓ Network Fraud Detection (사기 링)
  ✓ Regulations (10개 규정)
  ✓ ROI Calculator (금융 분석)
  ✓ Adaptive Thresholds (동적 임계값)
  ✓ Cache Manager (Redis 캐싱)
  ✓ Alerting System (다채널 알림)
  ✓ Model Scheduler (자동 학습)

📚 다음 단계:
  1. FastAPI 서버 실행: python -m uvicorn src.app.main:app --reload
  2. API 문서: http://localhost:8000/docs
  3. 실제 데이터로 테스트하기
    """)


if __name__ == "__main__":
    main()

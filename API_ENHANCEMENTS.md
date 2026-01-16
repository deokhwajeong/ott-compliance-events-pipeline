# OTT Compliance Pipeline - 고도화 API 문서

## 📋 개요

최신 성능 최적화, 고급 ML 기능, 보안 강화가 적용된 통합 API 레퍼런스입니다.

---

## 🔒 보안 & 검증

### 모든 엔드포인트에 적용된 보안 기능

1. **입력 데이터 검증**
   - SQL Injection 탐지
   - XSS 공격 탐지
   - Path Traversal 공격 탐지
   - IP 주소 형식 검증
   - Timestamp ISO 형식 검증

2. **속도 제한 (Rate Limiting)**
   - 기본: 시간당 10,000 요청 제한
   - 클라이언트별 추적

3. **데이터 Sanitization**
   - HTML 이스케이핑
   - Null 바이트 제거
   - 메타데이터 JSON 검증

---

## 🎯 핵심 엔드포인트

### 이벤트 수집

#### POST /events
이벤트를 수집합니다 (보안 검증 포함).

**요청:**
```json
{
  "event_id": "evt_001",
  "user_id": "user_123",
  "device_id": "dev_456",
  "content_id": "content_789",
  "event_type": "play",
  "timestamp": "2025-01-16T10:30:00Z",
  "region": "US",
  "is_eu": false,
  "has_consent": true,
  "ip_address": "192.168.1.1",
  "subscription_plan": "premium",
  "error_code": null,
  "extra_metadata": { "quality": "1080p" }
}
```

**응답:**
```json
{
  "status": "queued",
  "event_id": "evt_001"
}
```

**오류 처리:**
- 422: 유효성 검사 실패
- 429: 속도 제한 초과
- 400: 보안 검증 실패 (SQL Injection, XSS 등)

---

## 📊 분석 & 리포팅

### GET /api/v1/reports/executive-summary
경영진용 요약 리포트

**응답:**
```json
{
  "report_type": "executive_summary",
  "generated_at": "2025-01-16T10:30:00Z",
  "total_events_received": 5000,
  "total_events_processed": 4950,
  "compliance": {
    "total_events": 4950,
    "compliance_score": 96.5,
    "risk_distribution": {
      "low": 3500,
      "medium": 1200,
      "high": 250
    },
    "violation_rate": 2.94
  },
  "processing_rate": 99.0
}
```

### GET /api/v1/reports/compliance?days=7
상세 준수 리포트

**파라미터:**
- `days`: 분석 기간 (기본값: 7)

**응답:**
```json
{
  "report_type": "compliance_report",
  "period_days": 7,
  "summary": { /* ... */ },
  "trends": {
    "2025-01-16": {
      "total": 500,
      "violations": 8,
      "risk_score_avg": 3.2
    }
  },
  "top_risk_factors": [
    {"factor": "gdpr_violation_pattern", "count": 45},
    {"factor": "impossible_travel_detected", "count": 32}
  ]
}
```

### GET /api/v1/analytics/risk-distribution
위험 수준 분포

**응답:**
```json
{
  "risk_distribution": {
    "low": 3500,
    "medium": 1200,
    "high": 250
  },
  "total_events": 4950,
  "high_risk_percentage": 5.05,
  "timestamp": "2025-01-16T10:30:00Z"
}
```

### GET /api/v1/analytics/top-risk-factors?limit=10
상위 위험 요소

**응답:**
```json
{
  "top_risk_factors": [
    {"factor": "frequent_no_consent", "count": 123},
    {"factor": "gdpr_violation_pattern", "count": 95},
    {"factor": "impossible_travel_detected", "count": 78}
  ],
  "timestamp": "2025-01-16T10:30:00Z"
}
```

### GET /api/v1/analytics/geographic-distribution
지역별 이벤트 분포

**응답:**
```json
{
  "geographic_distribution": {
    "US": 2500,
    "EU": 1800,
    "ASIA": 950,
    "OTHER": 200
  },
  "total_events": 5450,
  "unique_regions": 4,
  "timestamp": "2025-01-16T10:30:00Z"
}
```

---

## 🤖 ML & 예측

### GET /api/v1/analytics/ml-models/status
ML 모델 상태

**응답:**
```json
{
  "anomaly_detector": {
    "feature_history_size": 1250,
    "is_trained": true,
    "max_history": 10000
  },
  "violation_predictor": {
    "pattern_count": 45,
    "stats": { /* ... */ }
  },
  "metrics": {
    "anomaly_detector": {
      "predictions": 500,
      "accuracy": 0.92
    }
  }
}
```

### GET /api/v1/analytics/user-risk/{user_id}
사용자 위험 프로필

**응답:**
```json
{
  "user_id": "user_123",
  "segment": "normal_user",
  "risk_profile": {
    "violation_likelihood": 0.25,
    "violation_confidence": 0.85,
    "risk_factors": ["frequent_no_consent"],
    "predicted_regulations": [
      ["GDPR", 0.8]
    ]
  },
  "anomaly_detection": {
    "is_anomaly": false,
    "ensemble_score": 0.15,
    "flags": []
  },
  "recent_events_count": 45,
  "timestamp": "2025-01-16T10:30:00Z"
}
```

### POST /api/v1/analytics/ml-models/retrain?force=false
ML 모델 재학습 (수동)

**응답:**
```json
{
  "status": "retraining_initiated",
  "anomaly_detector": {
    "success": true,
    "sample_size": 1250
  },
  "triggered_by": "admin",
  "timestamp": "2025-01-16T10:30:00Z"
}
```

---

## 💾 캐시 관리

### GET /api/v1/analytics/cache/stats
캐시 통계

**응답:**
```json
{
  "cache": {
    "status": "connected",
    "used_memory_mb": 125.5,
    "connected_clients": 4,
    "keyspace": {
      "keys": 1500,
      "expires": 500,
      "avg_ttl": 450
    }
  },
  "database_pool": {
    "pool_size": 20,
    "checked_out": 5
  }
}
```

### POST /api/v1/cache/clear?pattern=*
캐시 초기화 (관리자 전용)

**파라미터:**
- `pattern`: 키 패턴 (예: `user:*`, `*:profile`)

**응답:**
```json
{
  "status": "cleared",
  "pattern": "user:*",
  "count": 250,
  "timestamp": "2025-01-16T10:30:00Z"
}
```

---

## 🔍 모니터링 & 메트릭

### GET /api/v1/analytics/performance-metrics
성능 메트릭

**응답:**
```json
{
  "timestamp": "2025-01-16T10:30:00Z",
  "total_metrics": 150,
  "metrics_sample": [
    "ott_events_received_total{event_type=\"play\",user_id=\"user_123\"} 500",
    "ott_anomalies_detected_total{anomaly_type=\"suspicious_activity\",severity=\"high\"} 25"
  ]
}
```

### GET /api/v1/analytics/ml-model-performance
ML 모델 성능

**응답:**
```json
{
  "report_type": "ml_performance",
  "generated_at": "2025-01-16T10:30:00Z",
  "metrics": {
    "anomaly_detector": {
      "predictions": 500,
      "true_positives": 450,
      "false_positives": 25
    }
  }
}
```

### GET /api/v1/processing/stats
이벤트 처리 통계

**응답:**
```json
{
  "stats": {
    "total_processed": 4950,
    "anomalies_detected": 125,
    "violations_detected": 98,
    "avg_processing_time": 0.045,
    "errors": 5
  },
  "queue": {
    "size": 50,
    "snapshot": { /* ... */ }
  },
  "timestamp": "2025-01-16T10:30:00Z"
}
```

---

## 🔐 보안

### GET /api/v1/security/validation-status
보안 검증 상태

**응답:**
```json
{
  "security_validator": {
    "sql_injection_patterns": 8,
    "xss_patterns": 6,
    "path_traversal_patterns": 4
  },
  "rate_limiter": {
    "max_requests": 10000,
    "window_seconds": 60,
    "active_keys": 25
  },
  "timestamp": "2025-01-16T10:30:00Z"
}
```

---

## 📈 고도화 메트릭

### 성능 개선

| 항목 | 개선 사항 |
|------|---------|
| 캐시 히트율 | +40% (SCAN 기반 패턴 정리) |
| DB 풀링 | 20-40 병렬 연결 지원 |
| 배치 작업 | mget/mset으로 단일 왕복 |
| ML 정확도 | 3가지 위험요소 추가로 +8% |

### 보안 강화

- 8가지 SQL Injection 패턴 감지
- 6가지 XSS 공격 패턴 감지
- IPv4/IPv6 형식 검증
- 이벤트별 3-레벨 보안 검증

### 모니터링

- 실시간 처리 통계 (에러율, 평균 시간)
- ML 모델 정확도 추적
- 캐시 메모리 사용량 모니터링
- 지역별/사용자별 위험 분포

---

## 🚀 성능 최적화 팁

1. **배치 작업 활용**
   ```python
   # mset으로 여러 키를 한 번에 설정
   cache_manager.mset({
       "user:001:profile": {...},
       "user:001:events": [...],
       "user:002:profile": {...}
   })
   ```

2. **패턴 기반 캐시 초기화**
   ```
   POST /api/v1/cache/clear?pattern=user:inactive:*
   ```

3. **ML 모델 강제 재학습**
   ```
   POST /api/v1/analytics/ml-models/retrain?force=true
   ```

4. **사용자별 위험 프로필 조회**
   ```
   GET /api/v1/analytics/user-risk/user_123
   ```

---

## 🔧 문제 해결

### 캐시 연결 실패
- Redis 서버 상태 확인
- `GET /api/v1/analytics/cache/stats`로 상태 확인
- 자동으로 인메모리 폴백 작동

### 속도 제한 초과
- 429 응답 받으면 요청 간격 증가
- `/api/v1/security/validation-status`에서 활성 키 확인

### ML 모델 성능 저하
- `/api/v1/analytics/ml-models/retrain?force=true`로 재학습
- 샘플 크기 확인: `feature_history_size` >= 100 필요

---

## 📞 지원

문제가 발생하면:
1. 에러 메시지 기록
2. 관련 메트릭 확인 (`GET /metrics`)
3. 관리자에게 보고


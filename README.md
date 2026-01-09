# OTT Compliance Events Pipeline

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Smart TV/OTT 플랫폼을 위한 이벤트 수집 및 분석 파이프라인으로, 개인정보 보호 및 이상 행동 감지를 위한 컴플라이언스 위험 엔진을 포함합니다.

## 📋 목차

- [✨ 주요 기능](#-주요-기능)
- [🏗️ 아키텍처](#️-아키텍처)
- [🚀 빠른 시작](#-빠른-시작)
- [📊 대시보드](#-대시보드)
- [🔐 인증](#-인증)
- [📚 API 문서](#-api-문서)
- [🛠️ 기술 스택](#️-기술-스택)
- [📁 프로젝트 구조](#-프로젝트-구조)
- [🧪 테스트](#-테스트)
- [🤝 기여](#-기여)
- [📄 라이선스](#-라이선스)

## ✨ 주요 기능

### 🎯 실시간 이벤트 처리
- Smart TV/OTT 플랫폼에서 발생하는 이벤트 수집 (재생, 일시정지, 탐색, 오류 등)
- 비동기 큐 기반 처리로 고성능 이벤트 스트리밍
- SQLite 데이터베이스를 통한 영속성 보장

### 🔍 고급 컴플라이언스 위험 감지
- **GDPR/CCPA 준수**: EU 사용자 동의 상태 및 캘리포니아 지역 처리
- **시간 창 기반 분석**: 1시간 내 다중 지역 접근 및 고빈도 활동 감지
- **ML 기반 이상 탐지**: scikit-learn을 활용한 통계적 이상 탐지
- **구독 플랜 영향**: 프리미엄/베이직 사용자별 위험 조정

### 📈 실시간 모니터링
- Chart.js 기반 인터랙티브 대시보드
- 위험 수준별 분포 차트 (낮음/중간/높음)
- 실시간 메트릭 업데이트 (5초 간격)

### 🔐 보안 인증
- JWT 기반 인증 시스템
- 역할 기반 접근 제어 (관리자/분석가)
- 안전한 비밀번호 해싱 (PBKDF2)

## 🏗️ 아키텍처

```
Smart TV Client ──► [Ingest API] ──► [Queue] ──► [Consumer Service]
                        │               │               │
                        ▼               ▼               ▼
                   [Validation]    [In-Memory]    [Risk Analysis]
                        │               │               │
                        ▼               ▼               ▼
                   [JWT Auth]     [Redis/Kafka     [Compliance Rules]
                                   (Future)]        │
                                                   ▼
                                             [Database]
                                             │
                                             ▼
                                       [Analytics APIs]
                                             │
                                             ▼
                                       [Web Dashboard]
```

### 핵심 컴포넌트

- **Ingest API**: FastAPI 기반 이벤트 수집 엔드포인트
- **Queue**: 인메모리 큐 (Redis/Kafka로 확장 가능)
- **Consumer**: 이벤트 처리 및 위험 분석
- **Database**: SQLite 기반 데이터 영속성
- **Dashboard**: 실시간 웹 인터페이스

## 🚀 빠른 시작

### 필수 요구사항

- Python 3.12+
- pip

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/deokhwajeong/ott-compliance-events-pipeline.git
cd ott-compliance-events-pipeline

# 2. 가상환경 생성 (선택사항)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 테스트 데이터 생성

```bash
# 가짜 이벤트 생성 (1000개, 10개 동시 요청)
python src/scripts/generate_fake_events.py --events 1000 --concurrency 10
```

## 📊 대시보드

웹 브라우저에서 `http://localhost:8000`으로 접속하여 실시간 대시보드를 확인할 수 있습니다.

### 기능
- **실시간 메트릭**: 이벤트 처리 통계 및 위험 분포
- **위험 차트**: 도넛 차트로 위험 수준 시각화
- **최근 결과**: 최근 처리된 이벤트 목록
- **관리자 기능**: 로그인 후 이벤트 처리 제어

## 🔐 인증

관리자 엔드포인트는 JWT 토큰 기반 인증이 필요합니다.

### 테스트 계정

| 사용자명 | 비밀번호 | 권한 |
|---------|---------|------|
| `admin` | `admin123` | 관리자 |
| `analyst` | `analyst123` | 분석가 |

### 로그인 방법

```bash
# 토큰 발급
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# 응답 예시
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 보호된 엔드포인트 사용

```bash
# 인증 헤더와 함께 요청
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/compliance/summary
```

## 📚 API 문서

### 공개 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `GET` | `/` | 웹 대시보드 |
| `GET` | `/api` | 헬스체크 |
| `POST` | `/events` | 이벤트 수집 |
| `POST` | `/token` | JWT 토큰 발급 |

### 보호된 엔드포인트 (인증 필요)

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/process/one` | 단일 이벤트 처리 |
| `POST` | `/process/drain` | 모든 대기 이벤트 처리 |
| `GET` | `/stats/summary` | 처리 통계 요약 |
| `GET` | `/results/latest` | 최근 처리 결과 |
| `GET` | `/compliance/summary` | 위험 수준 요약 |

### 이벤트 모델

```json
{
  "event_id": "evt_123",
  "user_id": "user_42",
  "device_id": "tv_lg_abc123",
  "content_id": "movie_987",
  "event_type": "PLAY",
  "timestamp": "2026-01-02T12:34:56Z",
  "region": "NL",
  "is_eu": true,
  "has_consent": false,
  "ip_address": "203.0.113.10",
  "subscription_plan": "premium",
  "error_code": null,
  "extra_metadata": {
    "app_version": "1.2.3",
    "network_type": "wifi"
  }
}
```

## 🛠️ 기술 스택

### 백엔드
- **Python 3.12+**: 메인 프로그래밍 언어
- **FastAPI**: 고성능 웹 프레임워크
- **SQLAlchemy**: ORM 및 데이터베이스 관리
- **Pydantic**: 데이터 검증 및 직렬화

### 머신러닝 & 분석
- **scikit-learn**: ML 기반 이상 감지
- **NumPy**: 수치 계산
- **Chart.js**: 데이터 시각화

### 보안
- **PyJWT**: JWT 토큰 처리
- **PassLib**: 비밀번호 해싱
- **python-multipart**: 폼 데이터 처리

### 개발 도구
- **pytest**: 단위 테스트
- **Alembic**: 데이터베이스 마이그레이션
- **Uvicorn**: ASGI 서버

## 📁 프로젝트 구조

```
ott-compliance-events-pipeline/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI 애플리케이션
│       ├── auth.py              # JWT 인증 시스템
│       ├── models.py            # SQLAlchemy 모델
│       ├── schemas.py           # Pydantic 스키마
│       ├── db.py                # 데이터베이스 연결
│       ├── queue.py             # 큐 구현
│       ├── consumer.py          # 이벤트 소비자
│       ├── compliance_rules.py  # 위험 분석 규칙
│       └── templates/
│           └── dashboard.html   # 웹 대시보드
├── scripts/
│   └── generate_fake_events.py  # 테스트 데이터 생성기
├── tests/
│   └── test_app.py             # 단위 테스트
├── requirements.txt            # Python 의존성
├── README.md                   # 프로젝트 문서
└── LICENSE                     # MIT 라이선스
```

## 🧪 테스트

```bash
# 모든 테스트 실행
pytest tests/

# 상세 출력
pytest tests/ -v

# 특정 테스트 실행
pytest tests/test_app.py::test_event_schema -v
```

## 🤝 기여

기여를 환영합니다! 이슈를 보고하거나 풀 리퀘스트를 보내주세요.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

**문의**: 문제가 있거나 질문이 있으시면 [이슈](https://github.com/deokhwajeong/ott-compliance-events-pipeline/issues)를 열어주세요.

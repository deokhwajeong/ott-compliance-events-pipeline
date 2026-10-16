from src.app.ml_models import MIN_TRAINING_SAMPLES, EnhancedAnomalyDetector


def normal_event(i):
    return {
        "timestamp": f"2026-01-0{1 + i % 5}T{18 + i % 5:02d}:{i % 60:02d}:00Z",
        "event_type": ["play", "pause", "seek", "stop"][i % 4],
        "is_eu": False,
        "has_consent": True,
        "subscription_plan": ["basic", "premium"][i % 2],
    }


def fresh_detector(tmp_path, monkeypatch):
    monkeypatch.setattr("src.app.ml_models.MODEL_DIR", tmp_path)
    return EnhancedAnomalyDetector()


def test_cold_start_does_not_flag(tmp_path, monkeypatch):
    det = fresh_detector(tmp_path, monkeypatch)
    result = det.ensemble_anomaly_detection(normal_event(0))
    assert result["is_anomaly"] is False
    assert det.isolation_forest is None


def test_fits_after_warmup_and_flags_outlier(tmp_path, monkeypatch):
    det = fresh_detector(tmp_path, monkeypatch)
    for i in range(MIN_TRAINING_SAMPLES + 5):
        det.ensemble_anomaly_detection(normal_event(i))
    assert det.isolation_forest is not None

    outlier = {
        "timestamp": "2026-01-04T03:00:00Z",
        "event_type": "login_failed",
        "error_code": "AUTH",
        "is_eu": True,
        "has_consent": False,
        "subscription_plan": "vip",
    }
    result = det.ensemble_anomaly_detection(outlier, record=False)
    assert result["isolation_forest"]["is_anomaly"] is True
    assert isinstance(result["is_anomaly"], bool)


def test_record_false_does_not_grow_history(tmp_path, monkeypatch):
    det = fresh_detector(tmp_path, monkeypatch)
    det.ensemble_anomaly_detection(normal_event(0), record=False)
    assert det.feature_history == []

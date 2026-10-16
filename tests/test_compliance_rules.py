from src.app.compliance_rules import evaluate_compliance


def test_clean_us_playback_is_low_risk(make_event):
    result = evaluate_compliance(make_event(subscription_plan="premium"))
    assert result["risk_level"] == "low"
    assert result["flags"] == []


def test_eu_playback_without_consent_is_flagged(make_event):
    result = evaluate_compliance(make_event(region="DE", is_eu=True, has_consent=False))
    assert "eu_privacy_violation" in result["flags"]
    assert "gdpr_consent_violation" in result["flags"]
    assert result["risk_level"] in {"medium", "high"}


def test_gpc_targeted_ad_is_flagged(make_event):
    event = make_event(event_type="ad_impression", extra_metadata={"gpc": True, "targeted": True})
    result = evaluate_compliance(event)
    assert "ccpa_ad_targeting_violation" in result["flags"]
    assert result["risk_level"] != "low"


def test_auth_errors_and_missing_ids(make_event):
    result = evaluate_compliance({"event_type": "login_failed"})
    assert {"missing_user_id", "missing_device_id", "auth_or_playback_error"} <= set(result["flags"])


def test_result_shape(make_event):
    result = evaluate_compliance(make_event())
    assert set(result) >= {"score", "risk_level", "flags", "detailed_findings"}
    assert result["detailed_findings"]["compliance_check"]["applicable_regulations"] == ["CCPA"]

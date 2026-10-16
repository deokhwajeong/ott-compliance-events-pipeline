from src.app.regulations import ComplianceChecker, Regulation, RegulationFramework


def check(event_type, region, **details):
    return ComplianceChecker().evaluate_event_compliance("sub-1", event_type, region, details)


def test_eu_member_states_map_to_gdpr():
    for code in ("EU", "DE", "FR", "IE"):
        assert RegulationFramework.get_regulations_for_region(code) == [Regulation.GDPR]


def test_ca_is_canada_not_california():
    assert RegulationFramework.get_regulations_for_region("CA") == [Regulation.PIPEDA]
    assert RegulationFramework.get_regulations_for_region("US") == [Regulation.CCPA]


def test_unmapped_region_has_no_rules():
    result = check("play", "JP", has_explicit_consent=False)
    assert result["applicable_regulations"] == []
    assert result["compliant"] is True


def test_gdpr_playback_without_consent_is_a_violation():
    result = check("play", "DE", has_explicit_consent=False)
    assert not result["compliant"]
    assert result["violations"][0]["regulation"] == "GDPR"
    assert result["violations"][0]["action"] == "consent"


def test_gdpr_playback_with_consent_is_compliant():
    assert check("play", "DE", has_explicit_consent=True)["compliant"]


def test_ccpa_is_opt_out_so_playback_needs_no_prior_consent():
    assert check("play", "US", has_explicit_consent=False)["compliant"]


def test_ccpa_targeted_ad_despite_gpc_signal():
    result = check("ad_impression", "US", gpc_signal=True, targeted_ad=True)
    assert not result["compliant"]
    assert result["violations"][0]["action"] == "ad_targeting"


def test_ccpa_contextual_ad_with_gpc_is_fine():
    assert check("ad_impression", "US", gpc_signal=True, targeted_ad=False)["compliant"]


def test_gdpr_targeted_ad_requires_consent():
    assert not check("ad_impression", "FR", targeted_ad=True, has_explicit_consent=False)["compliant"]
    assert check("ad_impression", "FR", targeted_ad=True, has_explicit_consent=True)["compliant"]


def test_strictest_requirements_take_shortest_breach_window():
    req = RegulationFramework.get_strictest_requirements([Regulation.GDPR, Regulation.CCPA])
    assert req["breach_notification_days"] == 30
    assert req["dpia_required"] is True

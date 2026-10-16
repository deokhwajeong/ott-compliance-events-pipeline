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
    result = check("play", "KR", has_explicit_consent=False)
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
    # GDPR Art. 33(1) is 72 hours, stored as 3 days.
    assert req["breach_notification_days"] == 3
    assert req["dpia_required"] is True


def test_japan_maps_to_appi():
    assert RegulationFramework.get_regulations_for_region("JP") == [Regulation.APPI]


def test_appi_playback_needs_no_prior_consent():
    # Use within the published purpose of use does not need consent under APPI.
    assert check("play", "JP", has_explicit_consent=False)["compliant"]


def test_appi_third_party_ad_sharing_without_consent_is_a_violation():
    result = check(
        "ad_impression", "JP", targeted_ad=True, third_party_share=True, has_explicit_consent=False
    )
    assert not result["compliant"]
    v = result["violations"][0]
    assert (v["regulation"], v["action"]) == ("APPI", "ad_targeting")
    assert "third-party" in v["reason"]


def test_appi_first_party_targeting_or_consented_sharing_is_fine():
    assert check("ad_impression", "JP", targeted_ad=True, third_party_share=False)["compliant"]
    assert check("ad_impression", "JP", targeted_ad=True, third_party_share=True, has_explicit_consent=True)[
        "compliant"
    ]


def test_deletion_quick_check_uses_each_regulations_period():
    def deletion(reg, days, **extra):
        return RegulationFramework.check_violation(
            "data_deletion", reg, {"deletion_time_days": days, **extra}
        )["violation"]

    assert not deletion(Regulation.CCPA, 45)
    assert deletion(Regulation.CCPA, 46)
    assert not deletion(Regulation.CCPA, 80, extended=True)
    assert deletion(Regulation.LGPD, 16)
    assert not deletion(Regulation.PIPEDA, 30)
    # PIPEDA has no statutory erasure extension, so "extended" does not help.
    assert deletion(Regulation.PIPEDA, 40, extended=True)


def test_access_quick_check_cites_the_statute():
    r = RegulationFramework.check_violation("data_access", Regulation.LGPD, {"access_time_days": 20})
    assert r["violation"]
    assert "LGPD Art. 19, II" in r["reason"]
    assert "statutory" in r["reason"]

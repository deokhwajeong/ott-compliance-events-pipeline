from datetime import date, datetime

from src.app.dsr import (
    DSR_DEADLINES,
    add_months,
    due_date,
    evaluate_request,
    extension_honored,
    get_deadline,
)


def d(s):
    return date.fromisoformat(s)


def t(s):
    return datetime.fromisoformat(s)


def test_add_months_clamps_to_month_end():
    assert add_months(d("2026-01-31"), 1) == d("2026-02-28")
    assert add_months(d("2028-01-31"), 1) == d("2028-02-29")
    assert add_months(d("2026-11-15"), 2) == d("2027-01-15")


def test_gdpr_is_one_calendar_month_extendable_by_two():
    rule = get_deadline("GDPR", "deletion")
    assert rule.statutory and "Art. 12(3)" in rule.citation
    assert due_date(rule, d("2026-03-10")) == d("2026-04-10")
    assert due_date(rule, d("2026-03-10"), extended=True) == d("2026-06-10")


def test_ccpa_is_45_days_extendable_once_by_45():
    rule = get_deadline("CCPA", "access")
    assert "1798.130(a)(2)(A)" in rule.citation
    assert due_date(rule, d("2026-01-01")) == d("2026-02-15")
    assert due_date(rule, d("2026-01-01"), extended=True) == d("2026-04-01")


def test_lgpd_access_is_15_days_with_no_extension():
    rule = get_deadline("LGPD", "access")
    assert rule.statutory and rule.extension == 0
    assert due_date(rule, d("2026-05-01"), extended=True) == d("2026-05-16")


def test_lgpd_deletion_period_is_marked_as_policy_not_statute():
    rule = get_deadline("LGPD", "deletion")
    assert rule.statutory is False
    assert "ANPD" in rule.citation


def test_pipeda_access_30_days_plus_30_and_no_statutory_erasure_deadline():
    access = get_deadline("PIPEDA", "access")
    assert access.statutory and (access.period, access.extension) == (30, 30)
    assert get_deadline("PIPEDA", "deletion").statutory is False


def test_appi_without_delay_is_tracked_as_policy_sla():
    for kind in ("access", "deletion"):
        rule = get_deadline("APPI", kind)
        assert rule.statutory is False
        assert "without delay" in rule.citation


def test_unmodeled_regulation_falls_back_and_says_so():
    rule = get_deadline("KVKK", "access")
    assert rule.statutory is False and rule.citation == "not modeled"


def test_every_statutory_rule_has_a_citation():
    for rule in DSR_DEADLINES.values():
        assert rule.citation and rule.note


def test_extension_counts_only_when_noticed_inside_the_first_period():
    rule = get_deadline("GDPR", "access")
    assert extension_honored(rule, d("2026-03-10"), d("2026-04-10"))
    assert not extension_honored(rule, d("2026-03-10"), d("2026-04-11"))
    assert not extension_honored(get_deadline("LGPD", "access"), d("2026-03-10"), d("2026-03-11"))


def test_status_on_time_closed():
    r = evaluate_request(["GDPR"], "deletion", t("2026-03-10T09:00"), completed_at=t("2026-04-10T18:00"))
    assert r["status"] == "on_time" and r["state"] == "closed"
    assert r["due"] == "2026-04-10"


def test_status_breached_when_closed_late():
    r = evaluate_request(["GDPR"], "deletion", t("2026-01-31T09:00"), completed_at=t("2026-03-01T09:00"))
    assert r["status"] == "breached"
    assert r["breached_regulations"] == ["GDPR"]


def test_status_open_overdue_and_at_risk():
    received = t("2026-01-01T00:00")
    assert evaluate_request(["CCPA"], "access", received, as_of=t("2026-02-16T00:00"))["status"] == "breached"
    assert evaluate_request(["CCPA"], "access", received, as_of=t("2026-02-10T00:00"))["status"] == "at_risk"
    assert evaluate_request(["CCPA"], "access", received, as_of=t("2026-01-20T00:00"))["status"] == "on_time"


def test_timely_extension_moves_the_deadline():
    r = evaluate_request(
        ["CCPA"],
        "deletion",
        t("2026-01-01T00:00"),
        completed_at=t("2026-03-20T00:00"),
        extension_noticed_at=t("2026-02-01T00:00"),
    )
    assert r["status"] == "on_time" and r["extended"] and r["due"] == "2026-04-01"


def test_late_extension_is_not_honored():
    r = evaluate_request(
        ["CCPA"],
        "deletion",
        t("2026-01-01T00:00"),
        completed_at=t("2026-03-20T00:00"),
        extension_noticed_at=t("2026-02-20T00:00"),
    )
    assert r["status"] == "breached" and r["late_extension"]


def test_earliest_deadline_binds_when_several_regulations_apply():
    r = evaluate_request(
        ["CCPA", "LGPD"], "access", t("2026-01-01T00:00"), completed_at=t("2026-01-20T00:00")
    )
    assert r["binding"]["regulation"] == "LGPD"
    assert r["breached_regulations"] == ["LGPD"]


def test_no_rule_pack():
    assert evaluate_request([], "access", t("2026-01-01T00:00"))["status"] == "no_rule"

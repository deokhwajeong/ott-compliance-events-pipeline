def test_health(client):
    assert client.get("/api").json() == {"message": "OTT Compliance Events Pipeline"}


def test_dashboard_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "OTT Compliance Events Pipeline" in r.text


def test_token_rejects_bad_password(client):
    r = client.post("/token", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_protected_endpoints_need_token(client):
    assert client.get("/compliance/summary").status_code in (401, 403)


def test_ingest_rejects_invalid_event_type(client, make_event):
    r = client.post("/events", json=make_event(event_type="teleport"))
    assert r.status_code == 422


def test_ingest_rejects_xss_payload(client, make_event):
    r = client.post("/events", json=make_event(content_id="<script>alert(1)</script>"))
    assert r.status_code == 400


def test_ingest_process_and_summarize(client, auth_headers, make_event):
    before = client.get("/compliance/summary", headers=auth_headers).json()["total_processed"]
    events = [
        make_event(user_id="sub-api-1"),
        make_event(user_id="sub-api-2", region="FR", is_eu=True, has_consent=False),
        make_event(
            user_id="sub-api-3",
            event_type="ad_impression",
            extra_metadata={"gpc": True, "targeted": True},
        ),
    ]
    for ev in events:
        assert client.post("/events", json=ev).status_code == 202

    results = client.post("/process/drain", headers=auth_headers).json()
    by_user = {r["event"]["user_id"]: r["result"] for r in results}
    assert "gdpr_consent_violation" in by_user["sub-api-2"]["flags"]
    assert "ccpa_ad_targeting_violation" in by_user["sub-api-3"]["flags"]

    summary = client.get("/compliance/summary", headers=auth_headers).json()
    assert summary["total_processed"] == before + 3

    latest = client.get("/results/latest?limit=3", headers=auth_headers).json()
    assert len(latest) == 3

    overview = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()
    assert overview["regulation_violations"]["GDPR"] >= 1
    regions = {r["region"]: r for r in overview["by_region"]}
    assert regions["FR"]["regulations"] == ["GDPR"]


def test_metrics_endpoint_is_prometheus_text(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# HELP" in r.text


def test_supported_regulations(client):
    body = client.get("/api/v1/regulations/supported").json()
    assert "GDPR" in body["regulations"] and "CCPA" in body["regulations"]


def test_analytics_endpoints_respond(client, auth_headers):
    for path in (
        "/api/v1/ml/status",
        "/api/v1/analytics/user-risk/sub-api-2",
        "/api/v1/reports/daily",
        "/api/v1/analytics/top-risk-factors",
    ):
        assert client.get(path, headers=auth_headers).status_code == 200, path
    r = client.post("/api/v1/ml/predict/violation?user_id=sub-api-2", headers=auth_headers)
    assert r.status_code == 200


def test_daily_report_is_computed_from_stored_events(client, auth_headers, make_event):
    client.post("/events", json=make_event(user_id="sub-rep-1", region="DE", is_eu=True, has_consent=False))
    client.post("/process/drain", headers=auth_headers)
    report = client.get("/api/v1/reports/daily", headers=auth_headers).json()
    assert report["gdpr_metrics"]["total_violations"] >= 1
    assert report["gdpr_metrics"]["events_in_scope"] >= report["gdpr_metrics"]["total_violations"]
    assert report["total_events"] >= 1
    html = client.get("/api/v1/reports/daily/html", headers=auth_headers)
    assert html.status_code == 200 and "GDPR Compliance Score" in html.text


def _dsr(make_event, event_type, request_id, ts, region="DE", user="sub-dsr-1", **extra):
    return make_event(
        user_id=user,
        event_type=event_type,
        timestamp=ts,
        region=region,
        is_eu=region == "DE",
        has_consent=False,
        extra_metadata={"request_id": request_id, **extra},
    )


def test_dsr_event_without_request_id_is_rejected(client, make_event):
    r = client.post("/events", json=make_event(event_type="dsr_deletion_request"))
    assert r.status_code == 422


def test_dsr_lifecycle_flags_late_gdpr_deletion(client, auth_headers, make_event):
    events = [
        # GDPR: received 31 Jan, one month ends 28 Feb, completed 1 Mar -> late.
        _dsr(make_event, "dsr_deletion_request", "dsr-api-late", "2026-01-31T10:00:00Z"),
        _dsr(make_event, "dsr_completed", "dsr-api-late", "2026-03-01T10:00:00Z"),
        # CCPA: extension noticed on day 31, completed on day 70 -> on time.
        _dsr(
            make_event,
            "dsr_access_request",
            "dsr-api-ext",
            "2026-01-01T10:00:00Z",
            region="US",
            user="sub-dsr-2",
        ),
        _dsr(
            make_event, "dsr_extension", "dsr-api-ext", "2026-02-01T10:00:00Z", region="US", user="sub-dsr-2"
        ),
        _dsr(
            make_event, "dsr_completed", "dsr-api-ext", "2026-03-12T10:00:00Z", region="US", user="sub-dsr-2"
        ),
        # Completion for a request that was never received.
        _dsr(make_event, "dsr_completed", "dsr-api-ghost", "2026-03-01T10:00:00Z"),
    ]
    for ev in events:
        assert client.post("/events", json=ev).status_code == 202, ev
    results = {
        r["event"]["event_id"]: r["result"]
        for r in client.post("/process/drain", headers=auth_headers).json()
    }
    flags = [results[ev["event_id"]]["flags"] for ev in events]

    assert "gdpr_data_deletion_violation" in flags[1] and "dsr_deadline_missed" in flags[1]
    # Withdrawn consent on a rights request is not itself a consent violation.
    assert "eu_privacy_violation" not in flags[0]
    assert not any(f.endswith("_violation") for f in flags[4])
    assert "dsr_unknown_request" in flags[5]

    body = client.get("/api/v1/dsr?as_of=2026-04-01T00:00:00Z", headers=auth_headers).json()
    by_id = {r["request_id"]: r for r in body["requests"]}
    assert by_id["dsr-api-late"]["status"] == "breached"
    assert by_id["dsr-api-late"]["due"] == "2026-02-28"
    assert by_id["dsr-api-ext"]["status"] == "on_time" and by_id["dsr-api-ext"]["extended"]
    assert "dsr-api-ghost" not in by_id
    assert body["summary"]["by_regulation"]["GDPR"]["breached"] >= 1


def test_dsr_open_request_becomes_overdue_with_time(client, auth_headers, make_event):
    ev = _dsr(
        make_event,
        "dsr_access_request",
        "dsr-api-open",
        "2026-05-01T10:00:00Z",
        region="BR",
        user="sub-dsr-3",
    )
    assert client.post("/events", json=ev).status_code == 202
    client.post("/process/drain", headers=auth_headers)

    def status(as_of):
        body = client.get(f"/api/v1/dsr?as_of={as_of}", headers=auth_headers).json()
        return {r["request_id"]: r for r in body["requests"]}["dsr-api-open"]["status"]

    assert status("2026-05-03T00:00:00Z") == "on_time"
    assert status("2026-05-10T00:00:00Z") == "at_risk"  # LGPD access: 15 days, due 16 May
    assert status("2026-05-17T00:00:00Z") == "breached"


def test_dsr_deadline_table_endpoint(client):
    body = client.get("/api/v1/dsr/deadlines").json()
    rows = {(r["regulation"], r["request_type"]): r for r in body["deadlines"]}
    assert rows[("CCPA", "deletion")]["period"] == 45
    assert rows[("GDPR", "access")]["unit"] == "months"
    assert "not legal advice" in body["disclaimer"]

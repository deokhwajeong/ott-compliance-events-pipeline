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

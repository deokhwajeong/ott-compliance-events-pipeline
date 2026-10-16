from src.app.security import RateLimiter, SecurityValidator


def test_detects_injection_patterns():
    assert SecurityValidator.is_xss_attempt("<script>alert(1)</script>")
    assert SecurityValidator.is_path_traversal_attempt("../../etc/passwd")
    assert not SecurityValidator.is_xss_attempt("title-001")


def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.is_allowed("a") and rl.is_allowed("a")
    assert not rl.is_allowed("a")
    assert rl.is_allowed("b")

from app.services.visitor_locale import normalize_public_ip


def test_normalize_public_ip_accepts_forwarded_public_address() -> None:
    assert normalize_public_ip("8.8.8.8, 10.0.0.1") == "8.8.8.8"


def test_normalize_public_ip_rejects_private_and_invalid_addresses() -> None:
    assert normalize_public_ip("10.0.0.1") is None
    assert normalize_public_ip("not-an-ip") is None
    assert normalize_public_ip(None) is None

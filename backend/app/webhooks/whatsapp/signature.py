import hashlib
import hmac


def compute_signature(app_secret: str, raw_body: bytes) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False

    expected = compute_signature(app_secret, raw_body)
    return hmac.compare_digest(expected, signature_header)

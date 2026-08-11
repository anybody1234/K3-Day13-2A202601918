from __future__ import annotations

import hashlib
import re

# Both the accented and the unaccented spelling: people type addresses either way.
_VN_ADDR_KW = (
    r"(?:đường|dường|duong|phường|phuong|phố|pho|quận|quan|huyện|huyen|"
    r"thành phố|thanh pho|tỉnh|tinh|thị trấn|thi tran|xã|ấp)"
)

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    # A house number anchors each segment, which both keeps ordinary prose ("đơn hàng 15
    # ngày") from matching and stops the trailing group from backtracking exponentially.
    # Case folding is scoped to this pattern: applying it globally would let `passport`
    # match lowercase text.
    "vn_address": rf"(?i:(?:\bsố\s*|\bso\s*)?\b\d{{1,4}}[\s,]+{_VN_ADDR_KW}\b[\s,]*[^\s,;]+"
    rf"(?:[\s,]+{_VN_ADDR_KW}\b[\s,]*[^\s,;]+)*)",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]

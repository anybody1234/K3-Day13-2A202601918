from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_vietnamese_addresses_with_and_without_accents() -> None:
    addresses = (
        "123 duong Le Loi, phuong Ben Nghe, quan 1",
        "123 đường Lê Lợi, phường Bến Nghé",
        "So 8 đường Nguyễn Huệ, quận 1, thành phố Hồ Chí Minh",
        "52 phố Hàng Bài, quận Hoàn Kiếm",
        "25 đường Trần Phú, phường 4, quận 5",
    )

    for address in addresses:
        out = scrub_text(f"Giao den {address} nhe")
        assert "REDACTED_VN_ADDRESS" in out
        assert address not in out


def test_address_pattern_leaves_ordinary_prose_alone() -> None:
    # A house number anchors the pattern, so prose that merely contains a number and a
    # word like "quan"/"pho" must survive untouched.
    prose = (
        "Đơn hàng 15 ngày chưa tới",
        "Toi da cho 3 ban xem roi",
        "Refund policy for order 12 items",
        "What is your refund policy?",
    )

    for text in prose:
        assert scrub_text(text) == text

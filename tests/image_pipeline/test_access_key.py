import pytest

from image_pipeline.access_key import find_key, is_valid_key, nfe_from_key

# Fictitious issuer data: no real CNPJ or key may be committed (public repo).
FAKE_CNPJ = "11222333000181"


def check_digit(body: str) -> int:
    total = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(body)))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def make_key(nfe: int = 4406833, model: str = "55", code: str = "12345678") -> str:
    # cUF + AAMM + CNPJ + model + series + nNF + tpEmis + cNF
    body = "35" + "2610" + FAKE_CNPJ + model + "001" + f"{nfe:09d}" + "1" + code
    assert len(body) == 43
    return body + str(check_digit(body))


def with_wrong_digit(key: str) -> str:
    return key[:43] + str((int(key[43]) + 1) % 10)


def key_with_remainder(remainder: int) -> str:
    for code in range(10_000_000, 10_100_000):
        body = make_key(code=str(code))[:43]
        total = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(body)))
        if total % 11 == remainder:
            return body + "0"
    raise AssertionError("no body found")


# Hand-checked value of make_key(): guards the helper against a wrong DV formula.
KNOWN_KEY = "35261011222333000181550010044068331123456783"


def test_helper_builds_the_known_key():
    assert make_key() == KNOWN_KEY


class TestIsValidKey:
    def test_accepts_a_valid_nfe_key(self):
        assert is_valid_key(make_key())

    def test_rejects_a_wrong_check_digit(self):
        assert not is_valid_key(with_wrong_digit(make_key()))

    def test_rejects_a_cte_key_even_with_a_valid_check_digit(self):
        assert not is_valid_key(make_key(model="57"))

    @pytest.mark.parametrize("remainder", [0, 1])
    def test_remainder_zero_or_one_gives_check_digit_zero(self, remainder):
        assert is_valid_key(key_with_remainder(remainder))

    @pytest.mark.parametrize("key", ["", make_key()[:43], make_key() + "0", make_key()[:20] + "x" + make_key()[21:]])
    def test_rejects_wrong_length_or_non_digits(self, key):
        assert not is_valid_key(key)


class TestNfeFromKey:
    def test_reads_the_invoice_number_without_leading_zeros(self):
        assert nfe_from_key(make_key(nfe=4406833)) == 4406833

    def test_reads_a_full_nine_digit_number(self):
        assert nfe_from_key(make_key(nfe=123456789)) == 123456789


class TestFindKey:
    def test_finds_a_bare_key(self):
        assert find_key(make_key()) == make_key()

    def test_finds_a_key_inside_a_url(self):
        text = f"http://example.com/consulta?chNFe={make_key()}&nVersao=100"
        assert find_key(text) == make_key()

    def test_ignores_43_digits(self):
        assert find_key(make_key()[:43]) is None

    def test_ignores_45_digits(self):
        assert find_key(make_key() + "1") is None

    def test_ignores_an_invalid_key(self):
        assert find_key(with_wrong_digit(make_key())) is None

    def test_ignores_a_cte_key(self):
        assert find_key(make_key(model="57")) is None

    @pytest.mark.parametrize("text", ["", "no digits here", "NOTA FISCAL 004406833"])
    def test_returns_none_without_a_key(self, text):
        assert find_key(text) is None

    def test_skips_an_invalid_key_and_returns_the_next_valid_one(self):
        text = f"{with_wrong_digit(make_key(nfe=1))} {make_key(nfe=2)}"
        assert find_key(text) == make_key(nfe=2)

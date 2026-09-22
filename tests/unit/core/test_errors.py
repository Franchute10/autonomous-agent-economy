import pytest

from aeos.core import DomainError


def test_domain_error_is_catchable_and_deterministic() -> None:
    error = DomainError("core.invalid", "The value is invalid")
    with pytest.raises(DomainError) as caught:
        raise error
    assert caught.value.code == "core.invalid"
    assert caught.value.message == "The value is invalid"
    assert str(caught.value) == "core.invalid: The value is invalid"


@pytest.mark.parametrize("code, message", [("", "message"), ("code", " ")])
def test_domain_error_rejects_blank_fields(code: str, message: str) -> None:
    with pytest.raises(ValueError):
        DomainError(code, message)

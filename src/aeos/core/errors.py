"""Provider- and transport-independent domain error contract."""


class DomainError(Exception):
    """A semantic domain failure with a stable code and useful message."""

    code: str
    message: str

    def __init__(self, code: str, message: str) -> None:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("domain error code must be a non-blank string")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("domain error message must be a non-blank string")
        self.code = code.strip()
        self.message = message.strip()
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

class ViceCityError(Exception):
    """Base exception for the bot."""


class InsufficientFundsError(ViceCityError):
    def __init__(self, account_type: str, current_balance: int, attempted_amount: int) -> None:
        self.account_type = account_type
        self.current_balance = current_balance
        self.attempted_amount = attempted_amount
        super().__init__(
            f"Insufficient funds in {account_type}. Current balance={current_balance}, attempted={attempted_amount}"
        )


class ConcurrentActionError(ViceCityError):
    """Raised when a user tries to run a duplicate action concurrently."""


class HeistDMValidationError(ViceCityError):
    def __init__(self, failed_user_ids: list[int]) -> None:
        self.failed_user_ids = failed_user_ids
        super().__init__(f"Failed DM validation for users: {failed_user_ids}")


class NotFoundError(ViceCityError):
    """Raised when a requested game entity is missing."""


class InvalidStateError(ViceCityError):
    """Raised when a command is not allowed for the current state."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from eventsourcing.domain.model.aggregate import BaseAggregateRoot

from bankaccounts.exceptions import AccountClosedError, InsufficientFundsError


class BankAccount(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.balance = Decimal("0.00")
        self.overdraft_limit = Decimal("0.00")
        self.is_closed = False

    def append_transaction(self, amount: Decimal, transaction_id: UUID = None) -> None:
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self.__trigger_event__(
            self.TransactionAppended, amount=amount, transaction_id=transaction_id
        )

    def check_account_is_not_closed(self) -> None:
        if self.is_closed:
            raise AccountClosedError({"account_id": self.id})

    def check_has_sufficient_funds(self, amount: Decimal) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise InsufficientFundsError({"account_id": self.id})

    class TransactionAppended(BaseAggregateRoot.Event):
        @property
        def amount(self) -> Decimal:
            return self.__dict__["amount"]

        def mutate(self, obj: "BankAccount") -> None:
            obj.balance += self.amount

    def set_overdraft_limit(self, overdraft_limit: Decimal) -> None:
        assert overdraft_limit > Decimal("0.00")
        self.check_account_is_not_closed()
        self.__trigger_event__(self.OverdraftLimitSet, overdraft_limit=overdraft_limit)

    class OverdraftLimitSet(BaseAggregateRoot.Event):
        @property
        def overdraft_limit(self) -> Decimal:
            return self.__dict__["overdraft_limit"]

        def mutate(self, obj: "BankAccount") -> None:
            obj.overdraft_limit = self.overdraft_limit

    def close(self):
        self.__trigger_event__(self.Closed)

    class Closed(BaseAggregateRoot.Event):
        def mutate(self, obj: "BankAccount") -> None:
            obj.is_closed = True

    def record_error(self, error: Exception, transaction_id=None):
        self.__trigger_event__(
            self.ErrorRecorded, error=error, transaction_id=transaction_id
        )

    class ErrorRecorded(BaseAggregateRoot.Event):
        @property
        def error(self):
            return self.__dict__["error"]

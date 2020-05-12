from decimal import Decimal
from typing import Any

from eventsourcing.domain.model.aggregate import BaseAggregateRoot

from bankaccounts.exceptions import TransactionError


class BankAccount(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.balance = Decimal("0.00")
        self.is_closed = False

    def append_transaction(self, amount: Decimal):
        if self.is_closed:
            raise TransactionError
        self.__trigger_event__(self.TransactionAppended, amount=amount)

    class TransactionAppended(BaseAggregateRoot.Event):
        @property
        def amount(self):
            return self.__dict__["amount"]

        def mutate(self, obj: "BankAccount") -> None:
            obj.balance += self.amount

    def close(self):
        self.__trigger_event__(self.Closed)

    class Closed(BaseAggregateRoot.Event):
        def mutate(self, obj: "BankAccount") -> None:
            obj.is_closed = True
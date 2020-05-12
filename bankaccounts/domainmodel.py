from decimal import Decimal
from typing import Any

from eventsourcing.domain.model.aggregate import BaseAggregateRoot


class BankAccount(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.balance = Decimal("0.00")

    def append_transaction(self, amount: Decimal):
        self.__trigger_event__(self.TransactionAppended, amount=amount)

    class TransactionAppended(BaseAggregateRoot.Event):
        def mutate(self, obj: "BankAccount") -> None:
            obj.balance += self.amount
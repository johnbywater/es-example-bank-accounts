from decimal import Decimal
from typing import Any
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.simple import SimpleApplication
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


class BankAccountApplication(SimpleApplication):
    def create_accout(self):
        account = BankAccount.__create__()
        self.save(account)
        return account.id

    def get_balance(self, account_id1):
        account = self.get_account(account_id1)
        return account.balance

    def get_account(self, account_id) -> BankAccount:
        account = self.repository[account_id]
        assert isinstance(account, BankAccount)
        return account

    def tranfer_funds(self, debit_account_id, credit_account_id, amount):
        debit_account = self.get_account(debit_account_id)
        credit_account = self.get_account(credit_account_id)
        debit_account.append_transaction(-amount)
        credit_account.append_transaction(amount)
        self.save([debit_account, credit_account])


class TestBankAccounts(TestCase):
    def test(self):
        with BankAccountApplication.mixin(PopoApplication)() as app:
            app: BankAccountApplication
            account_id1 = app.create_accout()
            account_id2 = app.create_accout()

            self.assertEqual(app.get_balance(account_id1), Decimal("0.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("0.00"))

            app.tranfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("100.00"),
            )

            self.assertEqual(app.get_balance(account_id1), -Decimal("100.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

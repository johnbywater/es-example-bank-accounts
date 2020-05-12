from decimal import Decimal
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication

from bankaccounts.application import BankAccountApplication


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

            self.assertEqual(app.get_balance(account_id1), Decimal("-100.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

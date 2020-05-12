from decimal import Decimal
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication

from bankaccounts.application import BankAccountApplication


class TestBankAccounts(TestCase):
    def test(self):
        with BankAccountApplication.mixin(PopoApplication)() as app:
            app: BankAccountApplication

            # Create an account.
            account_id1 = app.create_account()

            # Check balance.
            self.assertEqual(app.get_balance(account_id1), Decimal("0.00"))

            # Deposit funds.
            app.deposit_funds(
                credit_account_id=account_id1,
                amount=Decimal("1000.00")
            )

            # Check balance.
            self.assertEqual(app.get_balance(account_id1), Decimal("1000.00"))

            # Create another account.
            account_id2 = app.create_account()

            # Transfer funds.
            app.tranfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("100.00"),
            )

            # Check balances.
            self.assertEqual(app.get_balance(account_id1), Decimal("900.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

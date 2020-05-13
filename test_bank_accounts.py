from decimal import Decimal
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication

from bankaccounts.application import BankAccountApplication
from bankaccounts.exceptions import AccountClosedError, InsufficientFundsError, TransactionError


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
                amount=Decimal("200.00")
            )

            # Check balance.
            self.assertEqual(app.get_balance(account_id1), Decimal("200.00"))

            # Withdraw funds.
            app.withdraw_funds(
                credit_account_id=account_id1,
                amount=Decimal("50.00")
            )

            # Check balance.
            self.assertEqual(app.get_balance(account_id1), Decimal("150.00"))

            # Create another account.
            account_id2 = app.create_account()

            # Transfer funds.
            app.transfer_funds(
                debit_account_id=account_id1,
                credit_account_id=account_id2,
                amount=Decimal("100.00"),
            )

            # Check balances.
            self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

            # Fail to transfer funds - insufficient funds.
            with self.assertRaises(InsufficientFundsError):
                app.transfer_funds(
                    debit_account_id=account_id1,
                    credit_account_id=account_id2,
                    amount=Decimal("1000.00")
                )

            # Check balances - should be unchanged.
            self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
            self.assertEqual(app.get_balance(account_id2), Decimal("100.00"))

            # Close account.
            app.close_account(account_id1)

            # Fail to transfer funds - account closed.
            with self.assertRaises(AccountClosedError):
                app.transfer_funds(
                    debit_account_id=account_id1,
                    credit_account_id=account_id2,
                    amount=Decimal("50.00")
                )

            # Fail to deposit funds - account closed.
            with self.assertRaises(AccountClosedError):
                app.deposit_funds(
                    credit_account_id=account_id1,
                    amount=Decimal("1000.00")
                )

            # Fail to withdraw funds - insufficient funds.
            with self.assertRaises(InsufficientFundsError):
                app.withdraw_funds(
                    credit_account_id=account_id2,
                    amount=Decimal("500.00")
                )

            # Add overdraft.
            app.set_overdraft_limit(
                account_id=account_id2,
                overdraft_limit=Decimal("500.00")
            )

            # Withdraw funds.
            app.withdraw_funds(
                credit_account_id=account_id2,
                amount=Decimal("500.00")
            )

            # Check balance - should be overdrawn.
            self.assertEqual(app.get_balance(account_id2), Decimal("-400.00"))

            # Fail to set overdraft limit - account closed.
            with self.assertRaises(AccountClosedError):
                app.set_overdraft_limit(
                    account_id=account_id1,
                    overdraft_limit=Decimal("500.00")
                )


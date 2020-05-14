from decimal import Decimal
from unittest import TestCase

from eventsourcing.system.runner import SingleThreadedRunner

from bankaccounts.exceptions import AccountClosedError, InsufficientFundsError
from bankaccounts.system.definition import BankAccountSystem
from bankaccounts.system.accounts import Accounts
from bankaccounts.system.sagas import Sagas
from bankaccounts.system.commands import Commands


class TestBankAccountSystem(TestCase):
    def setUp(self) -> None:
        self.runner = SingleThreadedRunner(BankAccountSystem(infrastructure_class=None))
        self.runner.start()
        self.commands: Commands = self.runner.get(Commands)
        self.sagas: Sagas = self.runner.get(Sagas)
        self.accounts: Accounts = self.runner.get(Accounts)

    def tearDown(self) -> None:
        del self.accounts
        del self.sagas
        del self.commands
        self.runner.close()
        del self.runner

    def test_deposit_funds_ok(self):
        # Create an account.
        account_id1 = self.accounts.create_account()

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("0.00"))

        # Deposit funds.
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)
        self.assertFalse(self.sagas.get_saga(transaction_id).errors)

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))

    def test_deposit_funds_error_account_closed(self):
        # Create an account.
        account_id1 = self.accounts.create_account()

        # Close account.
        self.accounts.close_account(account_id1)

        # Deposit funds.
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], AccountClosedError({"account_id": account_id1}))

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("0.00"))

    def test_withdraw_funds_ok(self):
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Withdraw funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("50.00"))

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("150.00"))

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)
        self.assertFalse(self.sagas.get_saga(transaction_id).errors)

    def test_withdraw_funds_error_insufficient_funds(self):
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Fail to withdraw funds - insufficient funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("200.01"))

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], InsufficientFundsError({"account_id": account_id1}))

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))

    def test_withdraw_funds_error_account_closed(self):
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to withdraw funds - account closed.
        transaction_id = self.commands.withdraw_funds(
            debit_account_id=account_id1, amount=Decimal("50.00")
        )

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], AccountClosedError({"account_id": account_id1}))

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))

    def test_transfer_funds_ok(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Transfer funds.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("50.00"),
        )

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)
        self.assertFalse(self.sagas.get_saga(transaction_id).errors)

        # Check balances.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("150.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("50.00"))

    def test_transfer_funds_error_insufficient_funds(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Fail to transfer funds - insufficient funds.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("1000.00"),
        )

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], InsufficientFundsError({"account_id": account_id1}))

        # Check balances - should be unchanged.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("0.00"))

    def test_transfer_funds_error_debit_account_closed(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to transfer funds - account closed.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("50.00"),
        )

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], AccountClosedError({"account_id": account_id1}))

        # Check balances - should be unchanged.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("0.00"))

    def test_transfer_funds_error_credit_account_closed(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(account_id2, Decimal("200.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to transfer funds - account closed.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id2,
            credit_account_id=account_id1,
            amount=Decimal("50.00"),
        )

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], AccountClosedError({"account_id": account_id1}))

        # Check balances - should be unchanged.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("0.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("200.00"))

    def test_overdraft_limit(self):
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check overdraft limit.
        self.assertEqual(
            self.accounts.get_overdraft_limit(account_id1), Decimal("0.00")
        )

        # Set overdraft limit.
        self.accounts.set_overdraft_limit(
            account_id=account_id1, overdraft_limit=Decimal("500.00")
        )

        # Can't set negative overdraft limit.
        with self.assertRaises(AssertionError):
            self.accounts.set_overdraft_limit(
                account_id=account_id1, overdraft_limit=Decimal("-500.00")
            )

        # Check overdraft limit.
        self.assertEqual(
            self.accounts.get_overdraft_limit(account_id1), Decimal("500.00")
        )

        # Withdraw funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("500.00"))

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)
        self.assertFalse(self.sagas.get_saga(transaction_id).errors)

        # Check balance - should be overdrawn.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("-300.00"))

        # Fail to withdraw funds - insufficient funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("200.01"))

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], InsufficientFundsError({"account_id": account_id1}))

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("-300.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to set overdraft limit - account closed.
        with self.assertRaises(AccountClosedError):
            self.accounts.set_overdraft_limit(
                account_id=account_id1, overdraft_limit=Decimal("5000.00")
            )

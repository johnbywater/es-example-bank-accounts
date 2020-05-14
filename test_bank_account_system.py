from decimal import Decimal
from unittest import TestCase

from eventsourcing.system.runner import SingleThreadedRunner

from bankaccounts.exceptions import AccountClosedError, InsufficientFundsError
from bankaccounts.system import Accounts, BankAccountSystem, Commands, Sagas


class TestBankAccountSystem(TestCase):
    def setUp(self) -> None:
        self.runner = SingleThreadedRunner(BankAccountSystem(infrastructure_class=None))
        self.runner.start()
        self.commands: Commands = self.runner.get(Commands)
        self.sagas: Sagas = self.runner.get(Sagas)
        self.accounts: Accounts = self.runner.get(Accounts)

    def tearDown(self) -> None:
        self.accounts = None
        self.sagas = None
        self.commands = None
        self.runner.close()
        self.runner = None

    def test_deposit_funds(self):
        # Create an account.
        account_id1 = self.accounts.create_account()

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("0.00"))

        # Deposit funds.
        transaction_id = self.commands.deposit_funds(
            credit_account_id=account_id1, amount=Decimal("200.00")
        )

        # Check balance.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)
        self.assertFalse(self.sagas.get_saga(transaction_id).errors)

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
        transaction_id = self.commands.withdraw_funds(
            debit_account_id=account_id1, amount=Decimal("201.00")
        )

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        self.assertEqual(
            self.sagas.get_saga(transaction_id).errors[0],
            InsufficientFundsError({"account_id": account_id1}),
        )

    def test_transfer_funds_ok(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(
            credit_account_id=account_id1, amount=Decimal("200.00")
        )

        # Transfer funds.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("50.00"),
        )

        # Check saga succeeded.
        self.assertTrue(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertFalse(self.sagas.get_saga(transaction_id).has_errored)

        # Check balances.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("150.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("50.00"))

    def test_transfer_funds_error_insufficient_funds(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(
            credit_account_id=account_id1, amount=Decimal("200.00")
        )

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
        self.commands.deposit_funds(
            credit_account_id=account_id1, amount=Decimal("200.00")
        )
        self.commands.deposit_funds(
            credit_account_id=account_id2, amount=Decimal("200.00")
        )

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
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("200.00"))

    def test_transfer_funds_error_credit_account_closed(self):
        # Create accounts.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        self.commands.deposit_funds(
            credit_account_id=account_id1, amount=Decimal("200.00")
        )
        self.commands.deposit_funds(
            credit_account_id=account_id2, amount=Decimal("200.00")
        )

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to transfer funds - account closed.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id2,
            credit_account_id=account_id1,
            amount=Decimal("50.00"),
        )

        # Check balances - should be unchanged.
        self.assertEqual(self.accounts.get_balance(account_id1), Decimal("200.00"))
        self.assertEqual(self.accounts.get_balance(account_id2), Decimal("200.00"))

        # Check saga errored.
        self.assertFalse(self.sagas.get_saga(transaction_id).has_succeeded)
        self.assertTrue(self.sagas.get_saga(transaction_id).has_errored)
        errors = self.sagas.get_saga(transaction_id).errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], AccountClosedError({"account_id": account_id1}))

        # # Fail to withdraw funds - account closed.
        # with self.assertRaises(AccountClosedError):
        #     app.withdraw_funds(
        #         debit_account_id=account_id1, amount=Decimal("1.00")
        #     )
        #
        # # Fail to deposit funds - account closed.
        # with self.assertRaises(AccountClosedError):
        #     app.deposit_funds(
        #         debit_account_id=account_id1, amount=Decimal("1000.00")
        #     )
        #
        # # Check balance - should be unchanged.
        # self.assertEqual(app.get_balance(account_id1), Decimal("50.00"))
        #
        # # Check overdraft limit.
        # self.assertEqual(app.get_overdraft_limit(account_id2), Decimal("0.00"))
        #
        # # Set overdraft limit.
        # app.set_overdraft_limit(
        #     account_id=account_id2, overdraft_limit=Decimal("500.00")
        # )
        #
        # # Can't set negative overdraft limit.
        # with self.assertRaises(AssertionError):
        #     app.set_overdraft_limit(
        #         account_id=account_id2, overdraft_limit=Decimal("-500.00")
        #     )
        #
        # # Check overdraft limit.
        # self.assertEqual(app.get_overdraft_limit(account_id2), Decimal("500.00"))
        #
        # # Withdraw funds.
        # app.withdraw_funds(debit_account_id=account_id2, amount=Decimal("500.00"))
        #
        # # Check balance - should be overdrawn.
        # self.assertEqual(app.get_balance(account_id2), Decimal("-400.00"))
        #
        # # Fail to withdraw funds - insufficient funds.
        # with self.assertRaises(InsufficientFundsError):
        #     app.withdraw_funds(
        #         debit_account_id=account_id2, amount=Decimal("101.00")
        #     )
        #
        # # Fail to set overdraft limit - account closed.
        # with self.assertRaises(AccountClosedError):
        #     app.set_overdraft_limit(
        #         account_id=account_id1, overdraft_limit=Decimal("500.00")
        #     )

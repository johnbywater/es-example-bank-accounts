import os
from decimal import Decimal
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.system.definition import AbstractSystemRunner
from eventsourcing.system.multiprocess import MultiprocessRunner
from eventsourcing.system.runner import MultiThreadedRunner, SingleThreadedRunner

from bankaccounts.exceptions import AccountClosedError, InsufficientFundsError
from bankaccounts.system.definition import BankAccountSystem
from bankaccounts.system.accounts import Accounts
from bankaccounts.system.sagas import Sagas
from bankaccounts.system.commands import Commands


class TestSystemSingleThreadedPopo(TestCase):
    runner_class = SingleThreadedRunner
    infrastructure_class = PopoApplication
    runner: AbstractSystemRunner

    @classmethod
    def setUpClass(cls) -> None:
        # Run the system.
        cls.runner = cls.runner_class(
            BankAccountSystem(
                infrastructure_class=cls.infrastructure_class, setup_tables=True
            )
        )
        cls.runner.start()
        cls.commands: Commands = cls.runner.get(Commands)
        cls.sagas: Sagas = cls.runner.get(Sagas)
        cls.accounts: Accounts = cls.runner.get(Accounts)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.close()

    def test_deposit_funds_ok(self):
        # Create an account.
        account_id1 = self.accounts.create_account()

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("0.00"))

        # Deposit funds.
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check saga succeeded.
        self.assertSagaHasSucceeded(transaction_id)

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))

    def test_deposit_funds_error_account_closed(self):
        # Create an account.
        account_id1 = self.accounts.create_account()

        # Close account.
        self.accounts.close_account(account_id1)

        # Deposit funds.
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check saga errored.
        self.assertSagaHasNotSucceeded(
            transaction_id, [AccountClosedError({"account_id": account_id1})]
        )

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("0.00"))

    def test_withdraw_funds_ok(self):
        # Create an account and deposit funds.
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Withdraw funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("50.00"))

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("150.00"))

        # Check saga succeeded.
        self.assertSagaHasSucceeded(transaction_id)

    def test_withdraw_funds_error_insufficient_funds(self):
        # Create an account and deposit funds.
        account_id1 = self.accounts.create_account()
        self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Fail to withdraw funds - insufficient funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("200.01"))

        # Check saga errored.
        self.assertSagaHasNotSucceeded(
            transaction_id, [InsufficientFundsError({"account_id": account_id1})]
        )

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))

    def test_withdraw_funds_error_account_closed(self):
        # Create an account and deposit funds.
        account_id1 = self.accounts.create_account()
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))
        self.assertSagaHasSucceeded(transaction_id)

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to withdraw funds - account closed.
        transaction_id = self.commands.withdraw_funds(
            debit_account_id=account_id1, amount=Decimal("50.00")
        )

        # Check saga errored.
        self.assertSagaHasNotSucceeded(
            transaction_id, [AccountClosedError({"account_id": account_id1})]
        )

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))

    def test_transfer_funds_ok(self):
        # Create two accounts and deposit funds.
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
        self.assertSagaHasSucceeded(transaction_id)

        # Check balances.
        self.assertBalanceEquals(account_id1, Decimal("150.00"))
        self.assertBalanceEquals(account_id2, Decimal("50.00"))

    def test_transfer_funds_error_insufficient_funds(self):
        # Create two accounts and deposit funds.
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
        self.assertSagaHasNotSucceeded(
            transaction_id, [InsufficientFundsError({"account_id": account_id1})]
        )

        # Check balances - should be unchanged.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))
        self.assertBalanceEquals(account_id2, Decimal("0.00"))

    def test_transfer_funds_error_debit_account_closed(self):
        # Create two accounts and deposit funds.
        account_id1 = self.accounts.create_account()
        account_id2 = self.accounts.create_account()
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))

        # Check saga errored.
        self.assertSagaHasSucceeded(transaction_id)

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to transfer funds - account closed.
        transaction_id = self.commands.transfer_funds(
            debit_account_id=account_id1,
            credit_account_id=account_id2,
            amount=Decimal("50.00"),
        )

        # Check saga errored.
        self.assertSagaHasNotSucceeded(
            transaction_id, [AccountClosedError({"account_id": account_id1})]
        )

        # Check balances - should be unchanged.
        self.assertBalanceEquals(account_id1, Decimal("200.00"))
        self.assertBalanceEquals(account_id2, Decimal("0.00"))

    def test_transfer_funds_error_credit_account_closed(self):
        # Create two accounts and deposit funds.
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
        self.assertSagaHasNotSucceeded(
            transaction_id, [AccountClosedError({"account_id": account_id1})]
        )

        # Check balances - should be unchanged.
        self.assertBalanceEquals(account_id1, Decimal("0.00"))
        self.assertBalanceEquals(account_id2, Decimal("200.00"))

    def test_overdraft_limit(self):
        # Create an account and deposit funds.
        account_id1 = self.accounts.create_account()
        transaction_id = self.commands.deposit_funds(account_id1, Decimal("200.00"))
        self.assertSagaHasSucceeded(transaction_id)

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
        self.assertSagaHasSucceeded(transaction_id)

        # Check balance - should be overdrawn.
        self.assertBalanceEquals(account_id1, Decimal("-300.00"))

        # Fail to withdraw funds - insufficient funds.
        transaction_id = self.commands.withdraw_funds(account_id1, Decimal("200.01"))

        # Check saga errored.
        self.assertSagaHasNotSucceeded(
            transaction_id, [InsufficientFundsError({"account_id": account_id1})]
        )

        # Check balance.
        self.assertBalanceEquals(account_id1, Decimal("-300.00"))

        # Close account.
        self.accounts.close_account(account_id1)

        # Fail to set overdraft limit - account closed.
        with self.assertRaises(AccountClosedError):
            self.accounts.set_overdraft_limit(
                account_id=account_id1, overdraft_limit=Decimal("5000.00")
            )

    WAIT_TIME = .1
    MAX_ATTEMPTS = 25

    @retry(
        (AssertionError, RepositoryKeyError), max_attempts=MAX_ATTEMPTS, wait=WAIT_TIME
    )
    def assertSagaHasSucceeded(self, transaction_id):
        saga = self.get_saga(transaction_id)
        self.assertTrue(saga.has_succeeded, msg=saga.errors)
        self.assertFalse(saga.has_errored)
        self.assertEqual(saga.errors, [])

    @retry(
        (AssertionError, RepositoryKeyError), max_attempts=MAX_ATTEMPTS, wait=WAIT_TIME
    )
    def assertSagaHasNotSucceeded(self, transaction_id, expected_errors):
        saga = self.get_saga(transaction_id)
        self.assertTrue(saga.has_errored)
        self.assertFalse(saga.has_succeeded)
        self.assertEqual(saga.errors, expected_errors)

    @retry(AssertionError, max_attempts=MAX_ATTEMPTS, wait=WAIT_TIME)
    def assertBalanceEquals(self, account_id, expected_balance):
        self.assertEqual(self.accounts.get_balance(account_id), expected_balance)

    def get_saga(self, transaction_id):
        return self.sagas.get_saga(transaction_id)


class WithMultiThreaded(TestCase):
    runner_class = MultiThreadedRunner


class WithMultiprocessing(TestCase):
    runner_class = MultiprocessRunner


class WithSQLAlchemy(TestCase):
    infrastructure_class = SQLAlchemyApplication

    @classmethod
    def setUpClass(cls) -> None:
        host = os.getenv("MYSQL_HOST", "127.0.0.1")
        user = os.getenv("MYSQL_USER", "eventsourcing")
        password = os.getenv("MYSQL_PASSWORD", "eventsourcing")
        db_uri = (
            "mysql+pymysql://{}:{}@{}/eventsourcing?charset=utf8mb4&binary_prefix=true"
        ).format(user, password, host)
        os.environ["DB_URI"] = db_uri
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        try:
            del os.environ["DB_URI"]
        except KeyError:
            pass


class WithSQLAlchemyInMemory(TestCase):
    infrastructure_class = SQLAlchemyApplication


class TestSystemSingleThreadedSQLAlchemy(WithSQLAlchemy, TestSystemSingleThreadedPopo):
    pass


class TestSystemSingleThreadedSQLAlchemyInMemory(
    WithSQLAlchemyInMemory, TestSystemSingleThreadedPopo
):
    pass


class TestSystemMultiThreadedPopo(WithMultiThreaded, TestSystemSingleThreadedPopo):
    pass


class TestSystemMultiThreadedSQLAlchemy(
    WithMultiThreaded, WithSQLAlchemy, TestSystemSingleThreadedPopo
):
    pass


class TestSystemMultiprocessingSQLAlchemy(
    WithMultiprocessing, WithSQLAlchemy, TestSystemSingleThreadedPopo
):
    pass

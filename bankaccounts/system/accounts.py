from decimal import Decimal
from uuid import UUID

from eventsourcing.application.decorators import applicationpolicy
from eventsourcing.application.process import ProcessApplication

from bankaccounts.domainmodel import BankAccount
from bankaccounts.exceptions import TransactionError
from bankaccounts.system.sagas import (
    DepositFundsSaga,
    TransferFundsSaga,
    WithdrawFundsSaga,
)


class Accounts(ProcessApplication):
    def create_account(self) -> UUID:
        account = BankAccount.__create__()
        self.save(account)
        return account.id

    def get_account(self, repository, account_id: UUID) -> BankAccount:
        account = repository[account_id]
        assert isinstance(account, BankAccount)
        return account

    def get_balance(self, account_id: UUID) -> Decimal:
        account = self.get_account(self.repository, account_id)
        return account.balance

    def set_overdraft_limit(self, account_id: UUID, overdraft_limit: Decimal) -> None:
        account = self.get_account(self.repository, account_id)
        account.set_overdraft_limit(overdraft_limit)
        self.save(account)

    def get_overdraft_limit(self, account_id: UUID) -> Decimal:
        account = self.get_account(self.repository, account_id)
        return account.overdraft_limit

    def close_account(self, account_id: UUID) -> None:
        account = self.get_account(self.repository, account_id)
        account.close()
        self.save(account)

    @applicationpolicy
    def policy(self, repository, event):
        pass

    @policy.register(DepositFundsSaga.Created)
    def _(self, repository, event):
        self._append_transaction(
            repository=repository,
            transaction_id=event.originator_id,
            account_id=event.credit_account_id,
            amount=event.amount,
        )

    @policy.register(WithdrawFundsSaga.Created)
    def _(self, repository, event):
        self._append_transaction(
            repository=repository,
            transaction_id=event.originator_id,
            account_id=event.debit_account_id,
            amount=-event.amount,
        )

    @policy.register(TransferFundsSaga.Created)
    def _(self, repository, event):
        self._append_transaction(
            repository=repository,
            transaction_id=event.originator_id,
            account_id=event.debit_account_id,
            amount=-event.amount,
        )

    @policy.register(TransferFundsSaga.CreditAccountCreditRequired)
    def _(self, repository, event):
        self._append_transaction(
            repository=repository,
            transaction_id=event.originator_id,
            account_id=event.credit_account_id,
            amount=event.amount,
        )

    @policy.register(TransferFundsSaga.DebitAccountRefundRequired)
    def _(self, repository, event):
        self._append_transaction(
            repository=repository,
            transaction_id=event.originator_id,
            account_id=event.debit_account_id,
            amount=event.amount,
        )

    def _append_transaction(self, repository, transaction_id, account_id, amount):
        account = self.get_account(repository=repository, account_id=account_id)
        try:
            account.append_transaction(amount, transaction_id=transaction_id)
        except TransactionError as e:
            account.record_error(error=e, transaction_id=transaction_id)

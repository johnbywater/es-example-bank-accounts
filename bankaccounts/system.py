from decimal import Decimal
from uuid import UUID

from eventsourcing.application.command import CommandProcess
from eventsourcing.application.decorators import applicationpolicy
from eventsourcing.application.process import ProcessApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.command import Command
from eventsourcing.system.definition import System

from bankaccounts.domainmodel import BankAccount
from bankaccounts.exceptions import TransactionError


class BaseCommand(Command):
    __subclassevents__ = True


class DepositFundsCommand(BaseCommand):
    def __init__(self, *, credit_account_id, amount, **kwargs):
        super(DepositFundsCommand, self).__init__(**kwargs)
        self.credit_account_id = credit_account_id
        self.amount = amount


class WithdrawFundsCommand(BaseCommand):
    def __init__(self, *, debit_account_id, amount, **kwargs):
        super(WithdrawFundsCommand, self).__init__(**kwargs)
        self.debit_account_id = debit_account_id
        self.amount = amount


class TransferFundsCommand(BaseCommand):
    def __init__(self, *, debit_account_id, credit_account_id, amount, **kwargs):
        super(TransferFundsCommand, self).__init__(**kwargs)
        self.debit_account_id = debit_account_id
        self.credit_account_id = credit_account_id
        self.amount = amount


class Commands(CommandProcess):
    def deposit_funds(self, credit_account_id, amount):
        self.save(
            DepositFundsCommand.__create__(
                credit_account_id=credit_account_id, amount=amount
            )
        )

    def withdraw_funds(self, debit_account_id, amount):
        self.save(
            WithdrawFundsCommand.__create__(
                debit_account_id=debit_account_id, amount=amount
            )
        )

    def transfer_funds(self, debit_account_id, credit_account_id, amount):
        self.save(
            TransferFundsCommand.__create__(
                debit_account_id=debit_account_id,
                credit_account_id=credit_account_id,
                amount=amount,
            )
        )


class BaseSaga(BaseAggregateRoot):
    __subclassevents__ = True


class DepositFundsSaga(BaseSaga):
    def __init__(self, *, credit_account_id, amount, **kwargs):
        super(DepositFundsSaga, self).__init__(**kwargs)
        self.credit_account_id = credit_account_id
        self.amount = amount


class WithdrawFundsSaga(BaseSaga):
    def __init__(self, *, debit_account_id, amount, **kwargs):
        super(WithdrawFundsSaga, self).__init__(**kwargs)
        self.debit_account_id = debit_account_id
        self.amount = amount


class TransferFundsSaga(BaseSaga):
    def __init__(self, *, debit_account_id, credit_account_id, amount, **kwargs):
        super(TransferFundsSaga, self).__init__(**kwargs)
        self.debit_account_id = debit_account_id
        self.credit_account_id = credit_account_id
        self.amount = amount

    def on_bank_account_transaction_appended(self, event: BankAccount.TransactionAppended):
        if self.was_debit_account_debited(event):
            self.require_credit_account_credit()

    def was_debit_account_debited(self, event):
        return event.originator_id == self.debit_account_id and event.amount == -self.amount

    def require_credit_account_credit(self):
        self.__trigger_event__(
            self.CreditAccountCreditRequired,
            credit_account_id=self.credit_account_id,
            amount=self.amount,
        )

    class CreditAccountCreditRequired(BaseSaga.Event):
        pass

    def on_bank_account_error_recorded(self, event: BankAccount.ErrorRecorded):
        if self.has_credit_account_errored(event):
            self.require_debit_account_refund()

    def has_credit_account_errored(self, event):
        return event.originator_id == self.credit_account_id

    def require_debit_account_refund(self):
        self.__trigger_event__(
            self.DebitAccountRefundRequired,
            debit_account_id=self.debit_account_id,
            amount=self.amount,
        )

    class DebitAccountRefundRequired(BaseSaga.Event):
        pass


class Sagas(ProcessApplication):
    @applicationpolicy
    def policy(self, repository, event):
        pass

    @policy.register(DepositFundsCommand.Created)
    def _(self, repository, event):
        return DepositFundsSaga.__create__(
            originator_id=event.originator_id,
            credit_account_id=event.credit_account_id,
            amount=event.amount,
        )

    @policy.register(WithdrawFundsCommand.Created)
    def _(self, repository, event):
        return WithdrawFundsSaga.__create__(
            originator_id=event.originator_id,
            debit_account_id=event.debit_account_id,
            amount=event.amount,
        )

    @policy.register(TransferFundsCommand.Created)
    def _(self, repository, event):
        return TransferFundsSaga.__create__(
            originator_id=event.originator_id,
            debit_account_id=event.debit_account_id,
            credit_account_id=event.credit_account_id,
            amount=event.amount,
        )

    @policy.register(BankAccount.TransactionAppended)
    def _(self, repository, event):
        if event.transaction_id:
            saga: TransferFundsSaga = repository[event.transaction_id]
            saga.on_bank_account_transaction_appended(event)

    @policy.register(BankAccount.ErrorRecorded)
    def _(self, repository, event):
        if event.transaction_id:
            saga: TransferFundsSaga = repository[event.transaction_id]
            saga.on_bank_account_error_recorded(event)


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

    def close_account(self, account_id: UUID) -> None:
        account = self.get_account(self.repository, account_id)
        account.close()
        self.save(account)

    @applicationpolicy
    def policy(self, repository, event):
        pass

    @policy.register(DepositFundsSaga.Created)
    def _(self, repository, event):
        account = self.get_account(
            repository=repository, account_id=event.credit_account_id
        )
        account.append_transaction(event.amount)

    @policy.register(WithdrawFundsSaga.Created)
    def _(self, repository, event):
        account = self.get_account(
            repository=repository, account_id=event.debit_account_id
        )
        account.append_transaction(-event.amount)

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


class BankAccountSystem(System):
    def __init__(self, infrastructure_class):
        super(BankAccountSystem, self).__init__(
            Commands | Sagas | Accounts | Sagas,
            infrastructure_class=infrastructure_class,
        )
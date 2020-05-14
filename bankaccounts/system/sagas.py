from eventsourcing.application.decorators import applicationpolicy
from eventsourcing.application.process import ProcessApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot

from bankaccounts.domainmodel import BankAccount
from bankaccounts.system.commands import (
    DepositFundsCommand,
    TransferFundsCommand,
    WithdrawFundsCommand,
)


class BaseSaga(BaseAggregateRoot):
    __subclassevents__ = True

    def __init__(self, **kwargs):
        super(BaseSaga, self).__init__(**kwargs)
        self.has_succeeded = False
        self.has_errored = False
        self.errors = []

    def on_bank_account_transaction_appended(self, event):
        self.record_has_succeeded()

    def record_has_succeeded(self):
        self.__trigger_event__(self.Succeeded)

    class Succeeded(BaseAggregateRoot.Event):
        def mutate(self, obj: "DepositFundsSaga") -> None:
            obj.has_succeeded = True

    def on_bank_account_error_recorded(self, event):
        self.record_has_errored(event.error)

    def record_has_errored(self, error=None):
        self.__trigger_event__(self.Errored, error=error)

    class Errored(BaseAggregateRoot.Event):
        @property
        def error(self):
            return self.__dict__["error"]

        def mutate(self, obj: "BaseSaga") -> None:
            obj.has_errored = True
            if self.error:
                obj.errors.append(self.error)


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
        self.has_debit_account_debited = False

    def on_bank_account_transaction_appended(
            self, event: BankAccount.TransactionAppended
    ):
        if self.was_debit_account_debited(event):
            self.require_credit_account_credit()
        elif self.was_credit_account_credited(event):
            self.record_has_succeeded()
        elif self.was_debit_account_refunded(event):
            self.record_has_errored()

    def was_debit_account_debited(self, event):
        return (
                self.has_debit_account_debited is False
                and event.originator_id == self.debit_account_id
                and event.amount == -self.amount
        )

    def was_credit_account_credited(self, event):
        return (
                self.has_debit_account_debited is True
                and event.originator_id == self.credit_account_id
                and event.amount == self.amount
        )

    def was_debit_account_refunded(self, event):
        return (
                self.has_debit_account_debited is True
                and event.originator_id == self.debit_account_id
                and event.amount == self.amount
        )

    def require_credit_account_credit(self):
        self.__trigger_event__(
            self.CreditAccountCreditRequired,
            credit_account_id=self.credit_account_id,
            amount=self.amount,
        )

    class CreditAccountCreditRequired(BaseSaga.Event):
        def mutate(self, obj: "TransferFundsSaga") -> None:
            obj.has_debit_account_debited = True

    def on_bank_account_error_recorded(self, event: BankAccount.ErrorRecorded):
        if self.has_debit_account_errored(event):
            self.record_has_errored(event.error)
        elif self.has_credit_account_errored(event):
            self.require_debit_account_refund(credit_account_error=event.error)

    def has_debit_account_errored(self, event):
        return event.originator_id == self.debit_account_id

    def has_credit_account_errored(self, event):
        return event.originator_id == self.credit_account_id

    def require_debit_account_refund(self, credit_account_error):
        self.__trigger_event__(
            self.DebitAccountRefundRequired,
            debit_account_id=self.debit_account_id,
            amount=self.amount,
            credit_account_error=credit_account_error,
        )

    class DebitAccountRefundRequired(BaseSaga.Event):
        @property
        def credit_account_error(self):
            return self.__dict__["credit_account_error"]

        def mutate(self, obj: "TransferFundsSaga") -> None:
            obj.errors.append(self.credit_account_error)


class Sagas(ProcessApplication):
    def get_saga(self, transaction_id) -> BaseSaga:
        saga = self.repository[transaction_id]
        assert isinstance(saga, BaseSaga)
        return saga

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
        saga: BaseSaga = repository[event.transaction_id]
        saga.on_bank_account_transaction_appended(event)

    @policy.register(BankAccount.ErrorRecorded)
    def _(self, repository, event):
        if event.transaction_id:
            saga: BaseSaga = repository[event.transaction_id]
            saga.on_bank_account_error_recorded(event)

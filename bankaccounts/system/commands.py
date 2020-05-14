from uuid import UUID

from eventsourcing.application.command import CommandProcess
from eventsourcing.domain.model.command import Command


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
    def deposit_funds(self, credit_account_id, amount) -> UUID:
        cmd = DepositFundsCommand.__create__(
            credit_account_id=credit_account_id, amount=amount
        )
        self.save(cmd)
        return cmd.id

    def withdraw_funds(self, debit_account_id, amount):
        cmd = WithdrawFundsCommand.__create__(
            debit_account_id=debit_account_id, amount=amount
        )
        self.save(cmd)
        return cmd.id

    def transfer_funds(self, debit_account_id, credit_account_id, amount):
        cmd = TransferFundsCommand.__create__(
            debit_account_id=debit_account_id,
            credit_account_id=credit_account_id,
            amount=amount,
        )
        self.save(cmd)
        return cmd.id

from decimal import Decimal
from uuid import UUID

from eventsourcing.application.simple import SimpleApplication

from bankaccounts.domainmodel import BankAccount


class BankAccountApplication(SimpleApplication):
    def create_account(self) -> UUID:
        account = BankAccount.__create__()
        self.save(account)
        return account.id

    def get_account(self, account_id: UUID) -> BankAccount:
        account = self.repository[account_id]
        assert isinstance(account, BankAccount)
        return account

    def get_balance(self, account_id: UUID) -> Decimal:
        account = self.get_account(account_id)
        return account.balance

    def deposit_funds(self, credit_account_id: UUID, amount: Decimal) -> None:
        account = self.get_account(credit_account_id)
        account.append_transaction(amount)
        self.save(account)

    def withdraw_funds(self, credit_account_id: UUID, amount: Decimal) -> None:
        account = self.get_account(credit_account_id)
        account.append_transaction(-amount)
        self.save(account)

    def transfer_funds(self, debit_account_id: UUID, credit_account_id: UUID, amount: Decimal) -> None:
        debit_account = self.get_account(debit_account_id)
        credit_account = self.get_account(credit_account_id)
        debit_account.append_transaction(-amount)
        credit_account.append_transaction(amount)
        self.save([debit_account, credit_account])

    def close_account(self, account_id):
        account = self.get_account(account_id)
        account.close()
        self.save(account)

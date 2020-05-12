from eventsourcing.application.simple import SimpleApplication

from bankaccounts.domainmodel import BankAccount


class BankAccountApplication(SimpleApplication):
    def create_account(self):
        account = BankAccount.__create__()
        self.save(account)
        return account.id

    def get_balance(self, account_id1):
        account = self.get_account(account_id1)
        return account.balance

    def get_account(self, account_id) -> BankAccount:
        account = self.repository[account_id]
        assert isinstance(account, BankAccount)
        return account

    def tranfer_funds(self, debit_account_id, credit_account_id, amount):
        debit_account = self.get_account(debit_account_id)
        credit_account = self.get_account(credit_account_id)
        debit_account.append_transaction(-amount)
        credit_account.append_transaction(amount)
        self.save([debit_account, credit_account])
from eventsourcing.system.definition import System

from bankaccounts.system.accounts import Accounts
from bankaccounts.system.commands import Commands
from bankaccounts.system.sagas import Sagas


class BankAccountSystem(System):
    def __init__(self, infrastructure_class):
        super(BankAccountSystem, self).__init__(
            Commands | Sagas | Accounts | Sagas,
            infrastructure_class=infrastructure_class,
        )

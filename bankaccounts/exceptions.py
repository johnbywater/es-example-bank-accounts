class TransactionError(Exception):
    def __eq__(self, other):
        return self.args == other.args and type(self) == type(other)


class AccountClosedError(TransactionError):
    pass


class InsufficientFundsError(TransactionError):
    pass

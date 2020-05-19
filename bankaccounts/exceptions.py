from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.utils.transcoding import decoder, encoder


class TransactionError(Exception):
    def __eq__(self, other):
        return self.args == other.args and type(self) == type(other)


class AccountClosedError(TransactionError):
    pass


class InsufficientFundsError(TransactionError):
    pass


@encoder.register(TransactionError)
def encode_exception(obj):
    d = {"__exception__": {"__topic__": get_topic(type(obj)), "args": obj.args,}}
    return d


@decoder.register("__exception__")
def decode_exception(d):
    exception_class = resolve_topic(d["__exception__"]["__topic__"])
    return exception_class(*d["__exception__"]["args"])

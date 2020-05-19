from unittest.case import TestCase

from eventsourcing.system.ray import RayRunner

from test_bank_account_system import (
    TestSystemSingleThreadedPopo,
    WithSQLAlchemy,
    WithSQLAlchemyInMemory,
)


class WithRay(TestCase):
    runner_class = RayRunner


class TestSystemWithRayAndPopo(WithRay, TestSystemSingleThreadedPopo):
    pass


class TestSystemWithRayAndSQLAlchemyInMemory(
    WithRay, WithSQLAlchemyInMemory, TestSystemSingleThreadedPopo
):
    pass


class TestSystemWithRayAndSQLAlchemy(
    WithRay, WithSQLAlchemy, TestSystemSingleThreadedPopo
):
    pass


del TestSystemSingleThreadedPopo

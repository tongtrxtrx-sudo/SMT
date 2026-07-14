import unittest

from smt_guard.operator import OperatorSession


class OperatorSessionTests(unittest.TestCase):
    def test_requires_a_named_operator_and_normalizes_input(self) -> None:
        session = OperatorSession()

        with self.assertRaisesRegex(ValueError, "操作员"):
            session.require()

        session.sign_in("  OP-01  ")
        self.assertEqual("OP-01", session.require())

    def test_rejects_clearing_the_current_operator(self) -> None:
        session = OperatorSession("OP-01")

        with self.assertRaisesRegex(ValueError, "操作员"):
            session.sign_in("   ")

        self.assertEqual("OP-01", session.require())


if __name__ == "__main__":
    unittest.main()

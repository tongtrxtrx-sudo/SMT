import unittest

from smt_guard.verification import MaterialVerifier, VerificationResult


class ExactVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = MaterialVerifier()

    def test_exact_material_code_is_ok(self) -> None:
        self.assertEqual(
            VerificationResult.OK,
            self.verifier.verify("10002345", "10002345"),
        )

    def test_different_material_code_is_ng(self) -> None:
        self.assertEqual(
            VerificationResult.NG,
            self.verifier.verify("10002345", "10002346"),
        )

    def test_outer_whitespace_is_trimmed(self) -> None:
        self.assertEqual(
            VerificationResult.OK,
            self.verifier.verify("10002345", " 10002345 \r\n"),
        )

    def test_leading_zero_is_significant(self) -> None:
        self.assertEqual(
            VerificationResult.NG,
            self.verifier.verify("013000081", "13000081"),
        )

    def test_ng_can_be_followed_by_ok_for_same_material_requirement(self) -> None:
        first = self.verifier.verify("10002345", "10002346")
        second = self.verifier.verify("10002345", "10002345")

        self.assertEqual(VerificationResult.NG, first)
        self.assertEqual(VerificationResult.OK, second)


if __name__ == "__main__":
    unittest.main()

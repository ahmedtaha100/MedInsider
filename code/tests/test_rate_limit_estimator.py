import io
import json
import unittest
from contextlib import redirect_stdout

from scripts.estimate_rate_limit_feasibility import estimate_feasibility, main


class RateLimitEstimatorTests(unittest.TestCase):
    def test_combined_tpm_can_be_the_bottleneck(self):
        result = estimate_feasibility(
            label="openai",
            calls=1000,
            rpm=100,
            input_tokens_per_call=1000,
            output_tokens_per_call=0,
            tpm=50000,
        )

        self.assertEqual(result["bottleneck"]["name"], "tokens_per_minute")
        self.assertEqual(result["projected_wall_clock_minutes"], 20.0)
        self.assertEqual(result["projected_wall_clock_hours"], round(20 / 60, 4))

    def test_split_input_output_limits_can_be_the_bottleneck(self):
        result = estimate_feasibility(
            label="anthropic",
            calls=1000,
            rpm=1000,
            input_tokens_per_call=2000,
            output_tokens_per_call=1000,
            input_tpm=500000,
            output_tpm=200000,
        )

        self.assertEqual(result["bottleneck"]["name"], "output_tokens_per_minute")
        self.assertEqual(result["projected_wall_clock_minutes"], 5.0)

    def test_negative_tokens_per_call_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            estimate_feasibility(
                label="invalid",
                calls=10,
                rpm=10,
                input_tokens_per_call=-1,
            )
        self.assertIn("input_tokens_per_call", str(ctx.exception))

    def test_negative_output_tokens_per_call_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            estimate_feasibility(
                label="invalid",
                calls=10,
                rpm=10,
                output_tokens_per_call=-1,
            )
        self.assertIn("output_tokens_per_call", str(ctx.exception))

    def test_non_positive_calls_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            estimate_feasibility(
                label="invalid",
                calls=0,
                rpm=10,
            )
        self.assertIn("calls", str(ctx.exception))

    def test_missing_limits_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            estimate_feasibility(
                label="invalid",
                calls=10,
            )
        self.assertIn("at least one limit", str(ctx.exception))

    def test_fractional_token_totals_are_not_truncated(self):
        result = estimate_feasibility(
            label="fractional",
            calls=3,
            rpm=10,
            input_tokens_per_call=0.25,
            output_tokens_per_call=0.5,
        )

        self.assertEqual(result["total_input_tokens"], 0.75)
        self.assertEqual(result["total_output_tokens"], 1.5)
        self.assertEqual(result["total_tokens"], 2.25)

    def test_main_prints_json_summary(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(
                [
                    "--label",
                    "google",
                    "--calls",
                    "1200",
                    "--rpm",
                    "300",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["label"], "google")
        self.assertEqual(payload["bottleneck"]["name"], "requests_per_minute")

    def test_main_returns_error_json_for_invalid_limits(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(
                [
                    "--label",
                    "invalid",
                    "--calls",
                    "10",
                ]
            )

        self.assertEqual(exit_code, 1)
        payload = json.loads(stream.getvalue())
        self.assertIn("at least one limit", payload["error"])


if __name__ == "__main__":
    unittest.main()

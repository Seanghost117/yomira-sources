import unittest

from validate_repository import validate_download_policy


class DownloadPolicyValidationTests(unittest.TestCase):
    def test_accepts_supported_restrictive_policy(self):
        errors = []
        validate_download_policy(
            {
                "downloadPolicy": {
                    "transport": "automatic",
                    "maximumConcurrentPages": 1,
                    "maximumAttempts": 4,
                }
            },
            "definition.json",
            errors,
        )
        self.assertEqual(errors, [])

    def test_rejects_unsafe_transport_and_out_of_range_values(self):
        errors = []
        validate_download_policy(
            {
                "downloadPolicy": {
                    "transport": "directBackground",
                    "maximumConcurrentPages": 4,
                    "maximumAttempts": 0,
                }
            },
            "definition.json",
            errors,
        )
        self.assertEqual(len(errors), 3)
        self.assertTrue(all("definition.json" in error for error in errors))

    def test_rejects_non_string_transport_values(self):
        for transport in ([], {}):
            with self.subTest(transport=transport):
                errors = []
                validate_download_policy(
                    {
                        "downloadPolicy": {
                            "transport": transport,
                            "maximumConcurrentPages": 1,
                            "maximumAttempts": 4,
                        }
                    },
                    "definition.json",
                    errors,
                )
                self.assertEqual(
                    errors,
                    ["definition.json: downloadPolicy.transport is unsupported"],
                )


if __name__ == "__main__":
    unittest.main()

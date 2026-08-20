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

    def test_accepts_omitted_and_partial_camel_or_snake_case_policy(self):
        definitions = (
            {},
            {"downloadPolicy": {}},
            {"downloadPolicy": {"transport": "foregroundCore"}},
            {"downloadPolicy": {"maximum_attempts": 2}},
            {"download_policy": {"maximumConcurrentPages": 3}},
            {"download_policy": {"maximum_concurrent_pages": 1}},
        )

        for definition in definitions:
            with self.subTest(definition=definition):
                errors = []
                validate_download_policy(definition, "definition.json", errors)
                self.assertEqual(errors, [])

    def test_rejects_unsafe_snake_case_policy(self):
        errors = []
        validate_download_policy(
            {
                "download_policy": {
                    "transport": "directBackground",
                    "maximum_concurrent_pages": 4,
                    "maximum_attempts": 0,
                }
            },
            "definition.json",
            errors,
        )

        self.assertEqual(
            errors,
            [
                "definition.json: downloadPolicy.transport is unsupported",
                "definition.json: downloadPolicy.maximumConcurrentPages must be between 1 and 3",
                "definition.json: downloadPolicy.maximumAttempts must be between 1 and 4",
            ],
        )

    def test_rejects_non_object_and_boolean_numbers_with_qualified_labels(self):
        errors = []
        validate_download_policy(
            {
                "download_policy": {
                    "maximum_concurrent_pages": True,
                    "maximum_attempts": False,
                }
            },
            "nested.json",
            errors,
        )
        validate_download_policy(
            {"downloadPolicy": []},
            "non-object.json",
            errors,
        )

        self.assertEqual(
            errors,
            [
                "nested.json: downloadPolicy.maximumConcurrentPages must be an integer",
                "nested.json: downloadPolicy.maximumAttempts must be an integer",
                "non-object.json: downloadPolicy must be an object",
            ],
        )

    def test_accepts_inclusive_numeric_boundaries(self):
        for concurrent_pages, attempts in ((1, 1), (3, 4)):
            with self.subTest(
                concurrent_pages=concurrent_pages,
                attempts=attempts,
            ):
                errors = []
                validate_download_policy(
                    {
                        "downloadPolicy": {
                            "maximumConcurrentPages": concurrent_pages,
                            "maximumAttempts": attempts,
                        }
                    },
                    "definition.json",
                    errors,
                )
                self.assertEqual(errors, [])

    def test_rejects_duplicate_top_level_or_nested_aliases(self):
        cases = (
            {
                "downloadPolicy": {"maximumAttempts": 2},
                "download_policy": {"maximum_attempts": 1},
            },
            {
                "downloadPolicy": {
                    "maximumConcurrentPages": 1,
                    "maximum_concurrent_pages": 2,
                }
            },
        )

        for definition in cases:
            with self.subTest(definition=definition):
                errors = []
                validate_download_policy(definition, "definition.json", errors)
                self.assertEqual(len(errors), 1)
                self.assertIn("definition.json: downloadPolicy", errors[0])
                self.assertIn("must not define both", errors[0])


if __name__ == "__main__":
    unittest.main()

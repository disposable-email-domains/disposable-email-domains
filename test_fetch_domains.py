import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from fetch_domains import CleanTempMailFetcher, FETCHERS


class FakeResponse:
    def __init__(self, payload=None, response_error=None, json_error=None):
        self.payload = payload
        self.response_error = response_error
        self.json_error = json_error

    def raise_for_status(self):
        if self.response_error:
            raise self.response_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class CleanTempMailFetcherTest(unittest.TestCase):
    def test_fetcher_is_registered_once(self):
        registered = [fetcher for fetcher in FETCHERS if isinstance(fetcher, CleanTempMailFetcher)]

        self.assertEqual(len(registered), 1)

    def test_fetches_and_normalizes_domains(self):
        payload = {
            "success": True,
            "data": {
                "domains": [" Example.COM ", "", "  ", None, 123, "example.com", "Second.ORG"],
                "limit": 2000,
                "offset": 0,
                "total": 7,
            },
        }

        with patch("fetch_domains.get", return_value=FakeResponse(payload)) as mock_get:
            domains = CleanTempMailFetcher().fetch()

        self.assertEqual(domains, {"example.com", "second.org"})
        mock_get.assert_called_once_with(
            "https://cleantempmail.com/api/domains",
            params={"limit": 2000, "offset": 0},
            timeout=30,
        )

    def test_fetches_all_pages(self):
        pages = {
            0: {
                "success": True,
                "data": {
                    "domains": ["First.COM", "second.com"],
                    "limit": 2,
                    "offset": 0,
                    "total": 3,
                },
            },
            2: {
                "success": True,
                "data": {
                    "domains": [" Third.COM "],
                    "limit": 2,
                    "offset": 2,
                    "total": 3,
                },
            },
        }

        def get_page(url, params, timeout):
            return FakeResponse(pages[params["offset"]])

        with patch("fetch_domains.get", side_effect=get_page) as mock_get:
            domains = CleanTempMailFetcher().fetch()

        self.assertEqual(domains, {"first.com", "second.com", "third.com"})
        self.assertEqual(
            [call.kwargs["params"]["offset"] for call in mock_get.call_args_list],
            [0, 2],
        )
        self.assertEqual(
            [call.kwargs["params"]["limit"] for call in mock_get.call_args_list],
            [2000, 2000],
        )

    def test_rejects_malformed_responses(self):
        malformed = [
            None,
            {"success": False, "data": {}},
            {"success": True},
            {"success": True, "data": {"domains": "example.com", "limit": 2, "offset": 0, "total": 1}},
            {"success": True, "data": {"domains": [], "limit": 0, "offset": 0, "total": 1}},
            {"success": True, "data": {"domains": [], "limit": 2, "offset": 1, "total": 1}},
        ]

        for payload in malformed:
            with self.subTest(payload=payload):
                with patch("fetch_domains.get", return_value=FakeResponse(payload)):
                    stderr = io.StringIO()
                    with redirect_stderr(stderr):
                        self.assertEqual(CleanTempMailFetcher().fetch(), set())
                    self.assertIn("malformed response", stderr.getvalue())

    def test_returns_empty_on_http_error(self):
        response = FakeResponse(response_error=RuntimeError("service unavailable"))

        with patch("fetch_domains.get", return_value=response):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(CleanTempMailFetcher().fetch(), set())

    def test_discards_partial_results_after_an_error(self):
        first_page = FakeResponse(
            {
                "success": True,
                "data": {
                    "domains": ["first.com"],
                    "limit": 1,
                    "offset": 0,
                    "total": 2,
                },
            }
        )
        second_page = FakeResponse(json_error=ValueError("invalid JSON"))
        with patch("fetch_domains.get", side_effect=[first_page, second_page]):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(CleanTempMailFetcher().fetch(), set())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from flycall_data.runtime_resources import peak_rss_bytes


class RuntimeResourceTests(unittest.TestCase):
    def test_peak_rss_is_reported_as_positive_bytes(self) -> None:
        self.assertGreater(peak_rss_bytes(), 0)


if __name__ == "__main__":
    unittest.main()

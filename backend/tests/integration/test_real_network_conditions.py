"""
Integration tests with real network conditions - no mocks.

All tests use actual network operations and conditions.
"""
import socket
import time

import pytest
import requests


class TestRealNetworkConditions:
    """Test with real network conditions."""

    def test_real_timeout(self, real_network_timeout_url):
        """Test with real network timeout."""
        try:
            response = requests.get(real_network_timeout_url, timeout=1)
            # Should not reach here
            assert False, "Should have timed out"
        except requests.Timeout:
            # Real timeout error - test our code that handles this
            pass

    def test_real_connection_refused(self):
        """Test with real connection refused."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(("127.0.0.1", 49151))  # Ephemeral range; expect closed
            sock.close()
            pytest.skip("Port 49151 is actually available")
        except (ConnectionRefusedError, socket.timeout, OSError):
            # Real connection error
            pass

    def test_real_dns_error(self):
        """Test with real DNS error."""
        try:
            response = requests.get("http://nonexistent-domain-12345.com", timeout=2)
            pytest.skip("DNS actually resolved")
        except (requests.exceptions.ConnectionError, socket.gaierror):
            # Real DNS error
            pass

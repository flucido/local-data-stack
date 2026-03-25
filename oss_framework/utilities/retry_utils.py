#!/usr/bin/env python3
"""
Retry Utilities for Production Data Pipelines

Provides exponential backoff retry logic for API calls, database operations,
and network requests to improve reliability and handle transient failures.

Based on production best practices:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 60s
- Structured logging for retry attempts
- Configurable max attempts and timeouts
- Callback for max retries exceeded

Usage:
    from oss_framework.utilities.retry_utils import retry_with_backoff

    @retry_with_backoff(max_attempts=5)
    def fetch_api_data(url):
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

Dependencies:
    pip install tenacity structlog
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import structlog
import requests
from typing import Callable, Optional, Any
import logging

logger = structlog.get_logger()


def retry_with_backoff(
    max_attempts: int = 5,
    max_wait: int = 60,
    retry_on: tuple = (requests.exceptions.RequestException, ConnectionError, TimeoutError),
):
    """
    Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        max_wait: Maximum wait time between retries in seconds (default: 60)
        retry_on: Tuple of exception types to retry on

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3, max_wait=30)
        def api_call():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()

    Retry schedule:
        Attempt 1: Immediate
        Attempt 2: Wait 1s
        Attempt 3: Wait 2s
        Attempt 4: Wait 4s
        Attempt 5: Wait 8s
        (Max wait capped at max_wait seconds)
    """

    def retry_error_callback(retry_state):
        """Called when max retries exceeded"""
        logger.error(
            "max_retries_exceeded",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
            function=retry_state.fn.__name__,
        )

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, max=max_wait),
        retry=retry_if_exception_type(retry_on),
        retry_error_callback=retry_error_callback,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def retry_api_call(
    func: Callable, *args, max_attempts: int = 5, max_wait: int = 60, **kwargs
) -> Any:
    """
    Retry a function call with exponential backoff (functional interface).

    Args:
        func: Function to retry
        *args: Positional arguments to pass to func
        max_attempts: Maximum number of attempts
        max_wait: Maximum wait time between retries
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of successful function call

    Raises:
        Exception from last failed attempt

    Example:
        result = retry_api_call(
            requests.get,
            "https://api.example.com/data",
            max_attempts=3
        )
    """

    @retry_with_backoff(max_attempts=max_attempts, max_wait=max_wait)
    def _wrapper():
        return func(*args, **kwargs)

    return _wrapper()


class RetryableHTTPClient:
    """
    HTTP client with built-in retry logic for transient failures.

    Example:
        client = RetryableHTTPClient(max_attempts=5)
        response = client.get("https://api.example.com/data")
        data = response.json()
    """

    def __init__(
        self,
        max_attempts: int = 5,
        max_wait: int = 60,
        timeout: int = 30,
        headers: Optional[dict] = None,
    ):
        self.max_attempts = max_attempts
        self.max_wait = max_wait
        self.timeout = timeout
        self.headers = headers or {}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    @retry_with_backoff(max_attempts=5, max_wait=60)
    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> requests.Response:
        """GET request with retry logic"""
        response = self.session.get(url, params=params, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    @retry_with_backoff(max_attempts=5, max_wait=60)
    def post(
        self, url: str, data: Optional[dict] = None, json: Optional[dict] = None, **kwargs
    ) -> requests.Response:
        """POST request with retry logic"""
        response = self.session.post(url, data=data, json=json, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    def close(self):
        """Close session"""
        self.session.close()


# Example usage
if __name__ == "__main__":
    import time

    # Setup structured logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    # Example 1: Decorator pattern
    print("Example 1: Decorator pattern\n")

    attempt_count = 0

    @retry_with_backoff(max_attempts=3, max_wait=10)
    def flaky_api_call():
        """Simulates API call that fails twice then succeeds"""
        global attempt_count
        attempt_count += 1
        print(f"  Attempt {attempt_count}...")

        if attempt_count < 3:
            raise requests.exceptions.ConnectionError("Simulated connection error")

        return {"status": "success", "data": [1, 2, 3]}

    try:
        result = flaky_api_call()
        print(f"  ✅ Success after {attempt_count} attempts: {result}\n")
    except Exception as e:
        print(f"  ❌ Failed after {attempt_count} attempts: {e}\n")

    # Example 2: Functional pattern
    print("Example 2: Functional pattern\n")

    attempt_count = 0

    def another_flaky_call():
        global attempt_count
        attempt_count += 1
        print(f"  Attempt {attempt_count}...")

        if attempt_count < 4:
            raise ConnectionError("Simulated error")

        return "Success!"

    try:
        result = retry_api_call(another_flaky_call, max_attempts=5)
        print(f"  ✅ Success: {result}\n")
    except Exception as e:
        print(f"  ❌ Failed: {e}\n")

    # Example 3: HTTP client
    print("Example 3: Retryable HTTP client\n")

    client = RetryableHTTPClient(max_attempts=3, timeout=10)

    try:
        # This will succeed (httpbin.org is reliable)
        response = client.get("https://httpbin.org/get")
        print(f"  ✅ HTTP GET succeeded: {response.status_code}\n")
    except Exception as e:
        print(f"  ❌ HTTP GET failed: {e}\n")
    finally:
        client.close()

    print("✅ All examples completed")

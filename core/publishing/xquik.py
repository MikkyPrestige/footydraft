"""Optional Xquik publisher for approved drafts."""
from __future__ import annotations

from typing import Any, Callable

import requests

from config.settings import XQUIK_API_BASE_URL, XQUIK_API_KEY, XQUIK_POSTING_ENABLED

MAX_TWEET_LENGTH = 280


class XquikPublishError(RuntimeError):
    """Raised when an approved draft cannot be posted through Xquik."""


def _build_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/v1/x/tweets"


def _extract_tweet_ref(body: dict[str, Any]) -> str | None:
    tweet_id = body.get("tweetId")
    if tweet_id:
        return str(tweet_id)
    write_action_id = body.get("writeActionId")
    if write_action_id:
        return f"xquik_action_{write_action_id}"
    return None


def _error_message(response: requests.Response, body: dict[str, Any]) -> str:
    message = body.get("message") or body.get("error") or response.text
    return str(message).strip() or "unknown error"


def publish_tweet(
    text: str,
    post: Callable[..., requests.Response] = requests.post,
) -> str:
    """Post an approved draft through Xquik and return a tweet reference."""
    if not XQUIK_POSTING_ENABLED:
        raise XquikPublishError("Xquik posting is disabled. Set XQUIK_POSTING_ENABLED=1 first.")
    if not XQUIK_API_KEY:
        raise XquikPublishError("XQUIK_API_KEY is missing.")

    tweet_text = text.strip()
    if not tweet_text:
        raise XquikPublishError("Draft text is empty.")
    if len(tweet_text) > MAX_TWEET_LENGTH:
        raise XquikPublishError(f"Draft is {len(tweet_text)} characters. X posts must be 280 or fewer.")

    try:
        response = post(
            _build_endpoint(XQUIK_API_BASE_URL),
            headers={
                "Content-Type": "application/json",
                "x-api-key": XQUIK_API_KEY,
            },
            json={"text": tweet_text},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise XquikPublishError(f"Xquik request failed: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code >= 400:
        raise XquikPublishError(f"Xquik post failed ({response.status_code}): {_error_message(response, body)}")

    tweet_ref = _extract_tweet_ref(body)
    if tweet_ref is None:
        raise XquikPublishError("Xquik accepted the request but did not return a tweet reference.")
    return tweet_ref

"""Tests for the optional Xquik publisher."""

import pytest

from core.publishing import xquik


class FakeResponse:
    def __init__(self, status_code: int, body: dict, text: str = ""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        return self._body


def test_publish_tweet_posts_to_xquik(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(200, {"success": True, "tweetId": "12345"})

    monkeypatch.setattr(xquik, "XQUIK_POSTING_ENABLED", True)
    monkeypatch.setattr(xquik, "XQUIK_API_KEY", "test_key")
    monkeypatch.setattr(xquik, "XQUIK_API_BASE_URL", "https://xquik.test/")

    tweet_ref = xquik.publish_tweet("Match winner in stoppage time", post=fake_post)

    assert tweet_ref == "12345"
    assert calls == [
        (
            ("https://xquik.test/api/v1/x/tweets",),
            {
                "headers": {
                    "Content-Type": "application/json",
                    "x-api-key": "test_key",
                },
                "json": {"text": "Match winner in stoppage time"},
                "timeout": 30,
            },
        )
    ]


def test_publish_tweet_requires_enabled(monkeypatch):
    monkeypatch.setattr(xquik, "XQUIK_POSTING_ENABLED", False)
    monkeypatch.setattr(xquik, "XQUIK_API_KEY", "test_key")

    with pytest.raises(xquik.XquikPublishError, match="disabled"):
        xquik.publish_tweet("Draft")


def test_publish_tweet_surfaces_api_error(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse(401, {"message": "Unauthorized"})

    monkeypatch.setattr(xquik, "XQUIK_POSTING_ENABLED", True)
    monkeypatch.setattr(xquik, "XQUIK_API_KEY", "test_key")

    with pytest.raises(xquik.XquikPublishError, match="401"):
        xquik.publish_tweet("Draft", post=fake_post)

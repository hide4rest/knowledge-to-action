"""scraper.py のユニットテスト。"""

from unittest.mock import MagicMock, patch

import pytest

from src.scraper import _extract_body, _get_meta, _get_og, _get_tag_text, scrape
from src.models import ScrapedPage


_SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>テストページ</title>
  <meta property="og:title" content="OGPタイトル" />
  <meta property="og:description" content="OGP説明文" />
  <meta property="og:image" content="https://example.com/img.jpg" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="テストサイト" />
  <meta name="description" content="metaの説明文" />
</head>
<body>
  <nav>ナビゲーション</nav>
  <article>
    <p>本文の内容です。</p>
  </article>
  <footer>フッター</footer>
</body>
</html>"""


def _make_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.apparent_encoding = "utf-8"
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


@patch("src.scraper.requests.get")
def test_scrape_ogp_metadata(mock_get: MagicMock) -> None:
    mock_get.return_value = _make_response(_SAMPLE_HTML)
    page = scrape("https://example.com/")

    assert page.success
    assert page.title == "OGPタイトル"
    assert page.description == "OGP説明文"
    assert page.og_image == "https://example.com/img.jpg"
    assert page.og_type == "article"
    assert page.site_name == "テストサイト"


@patch("src.scraper.requests.get")
def test_scrape_fallback_to_title_tag(mock_get: MagicMock) -> None:
    html = "<html><head><title>fallback title</title></head><body></body></html>"
    mock_get.return_value = _make_response(html)
    page = scrape("https://example.com/")

    assert page.title == "fallback title"


@patch("src.scraper.requests.get")
def test_scrape_error_on_request_exception(mock_get: MagicMock) -> None:
    import requests
    mock_get.side_effect = requests.ConnectionError("接続エラー")
    page = scrape("https://example.com/")

    assert not page.success
    assert page.error is not None


@patch("src.scraper.requests.get")
def test_scrape_body_excludes_nav_footer(mock_get: MagicMock) -> None:
    mock_get.return_value = _make_response(_SAMPLE_HTML)
    page = scrape("https://example.com/")

    assert "本文の内容です" in page.body_text
    assert "ナビゲーション" not in page.body_text
    assert "フッター" not in page.body_text

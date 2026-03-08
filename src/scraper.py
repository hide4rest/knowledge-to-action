"""OGPメタデータ・ページ本文取得モジュール。"""

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import ScrapedPage

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}
_TIMEOUT = 10
_MAX_BODY_CHARS = 5000


def scrape(url: str) -> ScrapedPage:
    """URLからOGPメタデータと本文を取得する。

    Args:
        url: スクレイピング対象のURL。

    Returns:
        スクレイピング結果を格納したScrapedPageオブジェクト。
    """
    html = _fetch_html(url)
    if html is None:
        return ScrapedPage(url=url, error="ページの取得に失敗しました")

    soup = BeautifulSoup(html, "lxml")
    page = ScrapedPage(url=url)

    # OGPメタデータ取得
    page.title = _get_og(soup, "og:title") or _get_tag_text(soup, "title") or ""
    page.description = (
        _get_og(soup, "og:description")
        or _get_meta(soup, "description")
        or ""
    )
    page.og_image = _get_og(soup, "og:image")
    page.og_type = _get_og(soup, "og:type")
    page.site_name = _get_og(soup, "og:site_name")

    # ページ本文抽出
    page.body_text = _extract_body(soup)

    logger.debug("スクレイピング完了: %s (title=%s)", url, page.title[:50])
    return page


def _fetch_html(url: str) -> Optional[str]:
    """HTMLを取得する。失敗時は1回リトライする。

    Args:
        url: 取得対象のURL。

    Returns:
        HTML文字列。取得失敗時はNone。
    """
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.RequestException as e:
            logger.warning("取得失敗 (attempt=%d): %s — %s", attempt + 1, url, e)
            if attempt == 0:
                time.sleep(1)
    return None


def _get_og(soup: BeautifulSoup, property_name: str) -> Optional[str]:
    """OGPプロパティを取得する。

    Args:
        soup: BeautifulSoupオブジェクト。
        property_name: OGPプロパティ名（例: "og:title"）。

    Returns:
        プロパティ値。存在しない場合はNone。
    """
    tag = soup.find("meta", property=property_name)
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return None


def _get_meta(soup: BeautifulSoup, name: str) -> Optional[str]:
    """metaタグのname属性からcontentを取得する。

    Args:
        soup: BeautifulSoupオブジェクト。
        name: metaタグのname属性値。

    Returns:
        content値。存在しない場合はNone。
    """
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return None


def _get_tag_text(soup: BeautifulSoup, tag_name: str) -> Optional[str]:
    """指定タグのテキストを取得する。

    Args:
        soup: BeautifulSoupオブジェクト。
        tag_name: タグ名。

    Returns:
        テキスト。存在しない場合はNone。
    """
    tag = soup.find(tag_name)
    if tag:
        return tag.get_text(strip=True)
    return None


def _extract_body(soup: BeautifulSoup) -> str:
    """ページ本文のテキストを抽出する。

    不要なタグを除去し、主要コンテンツを推定して返す。

    Args:
        soup: BeautifulSoupオブジェクト。

    Returns:
        抽出されたテキスト（最大_MAX_BODY_CHARS文字）。
    """
    # 不要なタグを削除
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    # 主要コンテンツタグを優先
    content = None
    for selector in ["article", "main", '[role="main"]', ".content", "#content", ".post", ".entry"]:
        content = soup.select_one(selector)
        if content:
            break

    target = content if content else soup.find("body")
    if target is None:
        return ""

    text = target.get_text(separator="\n", strip=True)
    # 連続する空行を1行に圧縮
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:_MAX_BODY_CHARS]

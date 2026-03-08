"""データモデル定義。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Entry:
    """保存情報エントリー。"""

    url: str
    title: str
    description: str
    body_text: str
    og_image: Optional[str]
    source: str  # "manual" | "raindrop"
    created_at: datetime
    id: Optional[int] = None


@dataclass
class Analysis:
    """個別分析結果。"""

    entry_id: int
    summary: str
    category: str
    subcategory: str
    keywords: list[str]
    actionability: str  # "high" | "medium" | "low"
    intent_guess: str
    id: Optional[int] = None


@dataclass
class ScrapedPage:
    """スクレイピング結果。"""

    url: str
    title: str = ""
    description: str = ""
    body_text: str = ""
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    site_name: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """スクレイピングが成功したか。"""
        return self.error is None

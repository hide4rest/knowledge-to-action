"""pytest設定: プロジェクトルートをsys.pathに追加する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

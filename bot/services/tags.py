"""Shared quick-select tag lists. Plain constants, not a user-editable DB
table (unlike margin presets) - these are universal trading concepts, not
something that benefits from per-user customization, so keeping them fixed
avoids an entire second CRUD/UI surface for a secondary feature."""
from __future__ import annotations

SETUP_TAGS = ["Breakout", "Pullback", "Retest", "Reversal", "Trend", "Boshqa"]
EMOTION_TAGS = ["Rejalashtirilgan", "Ishonchli", "Shoshqaloq", "FOMO", "Revenge"]

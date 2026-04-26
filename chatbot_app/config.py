"""Shared configuration values, paths, and environment loading."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load local environment variables before any module asks for secrets.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CUSTOMER_DB_PATH = BASE_DIR / "customer.db"
OWNER_DB_PATH = BASE_DIR / "owner.db"

# Default widget/site settings used when a site has no saved override yet.
DEFAULT_CONFIG = {
    "bot_name": "AI Assistant",
    "status_text": "Online now",
    "greeting": "Hi! How can I help you today?",
    "accent_color": "#667eea",
    "accent_color_2": "#764ba2",
    "header_bg_1": "#1a1a2e",
    "header_bg_2": "#16213e",
    "window_bg": "#0f0f1a",
    "placeholder": "Type a message...",
    "footer_text": "Powered by AI",
    "icon_type": "svg",
    "icon_value": "",
    "window_width": 420,
    "window_height": 580,
    "bubble_radius": 16,
    "font_size": 13,
    "launcher_size": 60,
    "launcher_pos": "right",
    "bot_bubble_bg": "rgba(255,255,255,0.08)",
    "user_bubble_text": "#ffffff",
    "online_dot_color": "#4ade80",
    "font_family": "DM Sans",
    "show_timestamps": False,
    "auto_open_delay": 0,
    "sound_enabled": False,
    "personality": "friendly",
    "custom_rules": "",
    "bot_text_color": "#ddddf0",
    "user_text_color": "#ffffff",
    "input_bg": "#0f0f1a",
    "opt_btn_color": "rgba(255,255,255,0.07)",
    "link_color": "#667eea",
    "line_height": 1.45,
    "bubble_pad_h": 12,
    "bubble_pad_v": 8,
    "message_gap": 6,
    "header_pad": 14,
    "opt_btn_radius": 50,
    "input_radius": 12,
}


def get_admin_api_key() -> str:
    """Return the configured admin API key or fail fast during app startup."""
    admin_api_key = os.getenv("ADMIN_API_KEY")
    if not admin_api_key:
        raise EnvironmentError("ADMIN_API_KEY is not set.")
    return admin_api_key

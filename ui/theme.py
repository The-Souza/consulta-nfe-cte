"""Design tokens for the dark theme. UI code must take colors, fonts and sizes from here."""

import customtkinter as ctk

# Surfaces
BG = "#18181a"
TITLEBAR = "#141416"
TITLEBAR_BORDER = "#26262a"
TOPBAR = "#1f1f22"
TOPBAR_BORDER = "#2c2c31"
SURFACE = "#222225"
SURFACE_2 = "#2a2a2e"
INPUT_BG = "#141416"
BORDER = "#34343a"
BORDER_INPUT = "#3a3a40"

# Text
TEXT = "#ededef"
TEXT_MUTED = "#a0a0a8"
TEXT_LABEL = "#c4c4cc"
TEXT_ON_PRIMARY = "#ffffff"

# Actions
PRIMARY = "#1d7f55"
PRIMARY_HOVER = "#19704b"
PROGRESS = "#2fa572"
TRANSPARENT = "transparent"

# Scrollbar
SCROLLBAR_WIDTH = 10
SCROLLBAR_BUTTON = "#3f3f46"
SCROLLBAR_BUTTON_HOVER = "#5a5a63"

# Status tones: (text, background)
STATUS: dict[str, tuple[str, str]] = {
    "ok": ("#5ee39a", "#15301f"),
    "warning": ("#f5c451", "#33290c"),
    "error": ("#ff8a80", "#3a1717"),
    "connection": ("#ffb27a", "#3a2412"),
    "info": ("#7cb8ff", "#142a45"),
    "neutral": ("#c4c4cc", "#2e2e33"),
}

# Banners over the results table: (softer text, bottom line, button outline). The background is the
# STATUS background. ok/connection/info come from the design; the others follow the same tints.
BANNER: dict[str, tuple[str, str, str]] = {
    "ok": ("#c9f5da", "#24503a", "#2f7a52"),
    "warning": ("#fbe7b2", "#5c4a18", "#7a6322"),
    "error": ("#ffd2cd", "#6b2a2a", "#8a3a3a"),
    "connection": ("#ffd9bd", "#6b4220", "#8a5530"),
    "info": ("#cfe3ff", "#24476f", "#2f5f94"),
    "neutral": ("#dcdce2", "#3f3f46", "#55555d"),
}

# Side panel bars: a muted green, the selected item uses the ok text color and outline
PANEL_BAR = "#3f8f66"
SELECTED_BORDER = "#2f7a52"

# Done step of the upload header: the check over the PROGRESS circle
STEP_DONE_MARK = "#0f1f16"

# Radii
RADIUS_INPUT = 8
RADIUS_ICON = 10
RADIUS_CARD = 12
RADIUS_DIALOG = 14
RADIUS_CHIP = 999

# Spacing
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_XXL = 32

# Typography
FONT_FAMILY = "Roboto"
FONT_MONO = "Consolas"
FONT_SIZE_XS = 11
FONT_SIZE_SM = 12
FONT_SIZE_BODY = 13
FONT_SIZE_INPUT = 14
FONT_SIZE_MD = 15
FONT_SIZE_LG = 18
FONT_SIZE_XL = 20


def font(size: int = FONT_SIZE_BODY, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
    """Build a CTkFont. Must be called after the root window exists."""
    return ctk.CTkFont(family=FONT_MONO if mono else FONT_FAMILY, size=size, weight=weight)

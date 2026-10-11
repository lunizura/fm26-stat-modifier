"""
FM26 Tactical Telemetry UI Theme & Custom Widgets.

Provides Windows 11 DWM dark-mode integration, FM26 attribute tier color-coding,
interactive attribute stepper rows, and player scout result cards.
"""

import ctypes
from typing import Callable, Tuple
import customtkinter as ctk

from fm_schema import AttributeDef, PlayerRecord

# Tactical Data Hub Palette
BG_CANVAS = "#070B12"         # Deep pitch obsidian
BG_PANEL = "#0D131F"          # Primary tactical panel
BG_CARD = "#131C2E"           # Elevated player/stat card
BG_CARD_HOVER = "#19253D"     # Card hover state
BG_CARD_ACTIVE = "#162A3A"    # Selected player card
BG_INPUT = "#0A0F1A"          # Search & numeric input background

BORDER_SUBTLE = "#1E2B42"     # Hairline structural border
BORDER_ACTIVE = "#10B981"     # Active emerald border
BORDER_ACCENT = "#38BDF8"     # Tactical cyan border

TEXT_PRIMARY = "#F1F5F9"      # High-contrast alabaster
TEXT_SECONDARY = "#94A3B8"    # Muted slate label
TEXT_DIM = "#64748B"          # Metadata & UID text

ACCENT_EMERALD = "#10B981"    # Primary FM pitch emerald
ACCENT_EMERALD_HOVER = "#059669"
ACCENT_CYAN = "#38BDF8"       # Tactical sky blue
ACCENT_AMBER = "#F59E0B"      # Elite gold / warning
ACCENT_ROSE = "#F43F5E"       # Danger / high-impact preset
ACCENT_VIOLET = "#8B5CF6"     # Potential / wonderkid badge


def apply_windows_glass(window: ctk.CTk) -> None:
    """Applies Windows 11/10 DWM Immersive Dark Mode and Mica/Acrylic window styling."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_mode = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
        )

        # DWMWA_SYSTEMBACKDROP_TYPE = 38 (2 = Mica, 3 = Acrylic)
        backdrop_type = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 38, ctypes.byref(backdrop_type), ctypes.sizeof(backdrop_type)
        )

        # DWMWA_CAPTION_COLOR = 35 (Match BG_CANVAS #070B12 -> BGR 0x00120B07)
        caption_color = ctypes.c_int(0x00120B07)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
        )
    except Exception:
        pass


def get_stat_tier_colors(val_20: int, inverse: bool = False) -> Tuple[str, str]:
    """
    Returns (badge_bg_hex, badge_text_hex) for an FM26 attribute on the 1-20 scale.
    Automatically inverts tiers for negative traits (Injury Proneness, Dirtiness).
    """
    v = max(1, min(20, int(val_20)))
    effective = (21 - v) if inverse else v

    if effective >= 16:
        return ("#064E3B", "#34D399")  # Elite (16-20): Deep Emerald / Bright Mint
    if effective >= 11:
        return ("#0C4A6E", "#38BDF8")  # Good (11-15): Deep Sky / Tactical Cyan
    if effective >= 6:
        return ("#451A03", "#FBBF24")  # Average (6-10): Deep Amber / Gold
    return ("#1E293B", "#94A3B8")      # Low (1-5): Slate


def get_ca_tier_color(ca_val: int) -> str:
    """Returns text color hex for a Current/Potential Ability value (1-200)."""
    if ca_val >= 170:
        return "#34D399"
    if ca_val >= 145:
        return "#38BDF8"
    if ca_val >= 115:
        return "#FBBF24"
    return "#94A3B8"


class AttributeStepperRow(ctk.CTkFrame):
    """
    Compact, tactile row for inspecting and editing a single FM26 attribute (1-20).
    Includes attribute label, [-] button, color-coded value badge, and [+] button.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        attr_def: AttributeDef,
        initial_val: int,
        on_change: Callable[[int, int], None],
    ) -> None:
        super().__init__(
            master,
            corner_radius=6,
            fg_color="#0F1726",
            border_width=1,
            border_color="#19253B",
            height=32,
        )
        self.attr_def = attr_def
        self.value = max(1, min(20, int(initial_val)))
        self.on_change = on_change

        self.grid_columnconfigure(0, weight=1)

        label_text = f"{attr_def.name} *" if attr_def.inverse else attr_def.name
        self.lbl_name = ctk.CTkLabel(
            self,
            text=label_text,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#CBD5E1" if not attr_def.inverse else "#FDA4AF",
        )
        self.lbl_name.grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=3)

        self.btn_minus = ctk.CTkButton(
            self,
            text="-",
            width=24,
            height=22,
            corner_radius=5,
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#E2E8F0",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            command=self._decrement,
        )
        self.btn_minus.grid(row=0, column=1, padx=(2, 3), pady=3)

        bg_col, txt_col = get_stat_tier_colors(self.value, self.attr_def.inverse)
        self.lbl_val = ctk.CTkLabel(
            self,
            text=f"{self.value:2d}",
            width=32,
            height=22,
            corner_radius=5,
            fg_color=bg_col,
            text_color=txt_col,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        )
        self.lbl_val.grid(row=0, column=2, padx=2, pady=3)

        self.btn_plus = ctk.CTkButton(
            self,
            text="+",
            width=24,
            height=22,
            corner_radius=5,
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#E2E8F0",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            command=self._increment,
        )
        self.btn_plus.grid(row=0, column=3, padx=(3, 6), pady=3)

    def _decrement(self) -> None:
        if self.value > 1:
            self.set_value(self.value - 1, notify=True)

    def _increment(self) -> None:
        if self.value < 20:
            self.set_value(self.value + 1, notify=True)

    def set_value(self, new_val: int, notify: bool = False) -> None:
        self.value = max(1, min(20, int(new_val)))
        bg_col, txt_col = get_stat_tier_colors(self.value, self.attr_def.inverse)
        self.lbl_val.configure(text=f"{self.value:2d}", fg_color=bg_col, text_color=txt_col)
        if notify:
            self.on_change(self.attr_def.index, self.value)


class PlayerResultCard(ctk.CTkFrame):
    """
    Clickable scouting card in the left sidebar showing Player Name, Positions,
    Age/Birth Year, UID, and CA / PA badges.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        player: PlayerRecord,
        is_selected: bool,
        on_select: Callable[[PlayerRecord], None],
    ) -> None:
        super().__init__(
            master,
            corner_radius=8,
            fg_color=BG_CARD_ACTIVE if is_selected else BG_CARD,
            border_width=1,
            border_color=BORDER_ACTIVE if is_selected else BORDER_SUBTLE,
        )
        self.player = player
        self.on_select = on_select

        self.grid_columnconfigure(0, weight=1)

        # Row 0: Display Name + Position Pill
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 1))
        top_row.grid_columnconfigure(0, weight=1)

        lbl_name = ctk.CTkLabel(
            top_row,
            text=player.display_name,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FFFFFF" if is_selected else TEXT_PRIMARY,
        )
        lbl_name.grid(row=0, column=0, sticky="ew")

        pos_str = player.best_positions_str(3)
        lbl_pos = ctk.CTkLabel(
            top_row,
            text=pos_str,
            corner_radius=4,
            fg_color="#1E293B",
            text_color=ACCENT_CYAN,
            padx=6,
            pady=1,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
        )
        lbl_pos.grid(row=0, column=1, sticky="e", padx=(6, 0))

        # Row 1: Meta (Age, Born, UID) + CA / PA Badges
        bot_row = ctk.CTkFrame(self, fg_color="transparent")
        bot_row.grid(row=1, column=0, sticky="ew", padx=10, pady=(1, 7))
        bot_row.grid_columnconfigure(0, weight=1)

        meta_text = f"Age {player.age} ({player.birth_year})  |  ID {player.uid}"
        lbl_meta = ctk.CTkLabel(
            bot_row,
            text=meta_text,
            anchor="w",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM,
        )
        lbl_meta.grid(row=0, column=0, sticky="w")

        ca_col = get_ca_tier_color(player.ca)
        lbl_capa = ctk.CTkLabel(
            bot_row,
            text=f"CA {player.ca}  /  PA {player.pa}",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=ca_col,
        )
        lbl_capa.grid(row=0, column=1, sticky="e")

        # Bind click events across card and child widgets
        for widget in (self, top_row, bot_row, lbl_name, lbl_pos, lbl_meta, lbl_capa):
            widget.bind("<Button-1>", self._handle_click)

    def _handle_click(self, _event=None) -> None:
        self.on_select(self.player)

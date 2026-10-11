"""
Football Manager 26 Tactical Scout & Live Stat Modifier (Desktop GUI).

Features:
- Instant Name-Only player search across all ~46,500 players in active .fm saves
- Authentic FM26 3-Column Attribute Matrix (Technical, Mental, Physical + Hidden & GK)
- Verified Win32 memory patching for ACTUAL_PLAYER@db C++ objects (1-100 internal scale)
- One-Click Tactical Presets (Super Boost, Max CA/PA, Peak Physical, Finisher, Playmaker)
"""

from datetime import datetime
from pathlib import Path
import threading
import time
from tkinter import filedialog
from typing import Dict, List, Optional
import customtkinter as ctk

from fm_core import (
    FMController,
    PlayerMemoryTarget,
    apply_preset_to_player,
    get_fm_process,
)
from fm_database import FMDatabase, find_latest_fm26_save
from fm_schema import (
    ATTRS_BY_CATEGORY,
    POSITION_DEFS,
    PlayerRecord,
    to_display_attr,
    to_raw_attr,
)
from ui_components import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_EMERALD,
    ACCENT_EMERALD_HOVER,
    ACCENT_ROSE,
    ACCENT_VIOLET,
    AttributeStepperRow,
    BG_CANVAS,
    BG_CARD,
    BG_INPUT,
    BG_PANEL,
    BORDER_ACTIVE,
    BORDER_SUBTLE,
    PlayerResultCard,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    apply_windows_glass,
    get_ca_tier_color,
)

ctk.set_appearance_mode("Dark")


class FM26TacticalModifierApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("FM26 Tactical Scout & Live Stat Modifier")
        self.geometry("1260x820")
        self.minsize(1100, 720)
        self.configure(fg_color=BG_CANVAS)

        self.db = FMDatabase()
        self.fm_ctrl: Optional[FMController] = None
        self.current_player: Optional[PlayerRecord] = None
        self.current_targets: List[PlayerMemoryTarget] = []
        self.filter_mode: str = "all"
        self._search_after_id: Optional[str] = None

        self.attr_rows: Dict[int, AttributeStepperRow] = {}
        self.pos_entries: Dict[int, ctk.CTkEntry] = {}

        self._build_layout()
        self.after(150, lambda: apply_windows_glass(self))

        # Populate initial star list immediately, then index full save file in background
        self._refresh_search_results()
        initial_list = self.db.search_players("", limit=1)
        if initial_list:
            self.select_player(initial_list[0])

        self.after(100, self._start_background_services)

    def _ui_call(self, callback) -> None:
        """Thread-safe UI dispatcher that ignores calls before mainloop or after destroy."""
        try:
            self.after(0, callback)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # LOGGING & STATUS BAR
    # ------------------------------------------------------------------
    def log(self, message: str, status_color: str = TEXT_SECONDARY) -> None:
        def _update() -> None:
            ts = datetime.now().strftime("%H:%M:%S")
            self.lbl_status_bar.configure(text=f"[{ts}]  {message}", text_color=status_color)
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", f"[{ts}] {message}\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        self._ui_call(_update)

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_left_search_pane()
        self._build_right_editor_pane()
        self._build_bottom_status_bar()

    def _build_top_bar(self) -> None:
        top_bar = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_PANEL,
            border_width=1,
            border_color=BORDER_SUBTLE,
            height=60,
        )
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 8))
        top_bar.grid_columnconfigure(1, weight=1)

        # Left Brand Title
        brand_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        ctk.CTkLabel(
            brand_frame,
            text="FM26 TACTICAL SCOUT & STAT MODIFIER",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_frame,
            text="Name-Only Database Search  |  ACTUAL_PLAYER@db Live Memory Engine (1-100 Scale)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM,
        ).pack(anchor="w")

        # Right Status & Controls
        right_controls = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_controls.grid(row=0, column=2, sticky="e", padx=14, pady=8)

        self.lbl_db_badge = ctk.CTkLabel(
            right_controls,
            text=f"DB: {self.db.player_count} Star Players",
            corner_radius=6,
            fg_color="#111C2D",
            text_color=ACCENT_CYAN,
            padx=10,
            pady=4,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.lbl_db_badge.pack(side="left", padx=(0, 6))

        self.btn_load_save = ctk.CTkButton(
            right_controls,
            text="Load .fm Save",
            width=105,
            height=28,
            corner_radius=6,
            fg_color="#1E293B",
            hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._browse_save_file,
        )
        self.btn_load_save.pack(side="left", padx=(0, 12))

        self.lbl_proc_badge = ctk.CTkLabel(
            right_controls,
            text="SCANNING FOR FM26...",
            corner_radius=6,
            fg_color="#231B0A",
            text_color=ACCENT_AMBER,
            padx=10,
            pady=4,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self.lbl_proc_badge.pack(side="left", padx=(0, 6))

        self.btn_reconnect = ctk.CTkButton(
            right_controls,
            text="Reconnect",
            width=86,
            height=28,
            corner_radius=6,
            fg_color="#1E293B",
            hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self.probe_connection(quiet=False),
        )
        self.btn_reconnect.pack(side="left")

    def _build_left_search_pane(self) -> None:
        left_pane = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_PANEL,
            border_width=1,
            border_color=BORDER_SUBTLE,
            width=340,
        )
        left_pane.grid(row=1, column=0, sticky="nsew", padx=(14, 6), pady=(0, 8))
        left_pane.grid_propagate(False)
        left_pane.grid_columnconfigure(0, weight=1)
        left_pane.grid_rowconfigure(3, weight=1)

        # Search Header & Input
        search_hdr = ctk.CTkFrame(left_pane, fg_color="transparent")
        search_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        search_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            search_hdr,
            text="PLAYER NAME SEARCH",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=ACCENT_EMERALD,
        ).grid(row=0, column=0, sticky="w")

        self.lbl_match_count = ctk.CTkLabel(
            search_hdr,
            text="",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM,
        )
        self.lbl_match_count.grid(row=0, column=1, sticky="e")

        # Search Entry Box
        search_box = ctk.CTkFrame(left_pane, fg_color="transparent")
        search_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 6))
        search_box.grid_columnconfigure(0, weight=1)

        self.entry_search = ctk.CTkEntry(
            search_box,
            placeholder_text="Type player name (e.g. Ronaldo, Bruno, Vitinha)...",
            height=36,
            corner_radius=8,
            fg_color=BG_INPUT,
            border_color=BORDER_SUBTLE,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.entry_search.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.entry_search.bind("<KeyRelease>", self._on_search_key_release)
        self.entry_search.bind("<Return>", lambda _e: self._refresh_search_results())

        btn_search = ctk.CTkButton(
            search_box,
            text="Find",
            width=54,
            height=36,
            corner_radius=8,
            fg_color=ACCENT_EMERALD,
            hover_color=ACCENT_EMERALD_HOVER,
            text_color="#03140D",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._refresh_search_results,
        )
        btn_search.grid(row=0, column=1)

        # Quick Filter Chips
        chip_row = ctk.CTkFrame(left_pane, fg_color="transparent")
        chip_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.filter_buttons: Dict[str, ctk.CTkButton] = {}
        for mode_id, label in [
            ("all", "Top Stars"),
            ("portugal", "Portugal"),
            ("wonderkids", "Wonderkids"),
        ]:
            btn = ctk.CTkButton(
                chip_row,
                text=label,
                height=25,
                corner_radius=6,
                fg_color="#1E293B" if mode_id != "all" else ACCENT_CYAN,
                text_color=TEXT_SECONDARY if mode_id != "all" else "#04131F",
                hover_color="#334155",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda m=mode_id: self._set_filter_mode(m),
            )
            btn.pack(side="left", fill="x", expand=True, padx=2)
            self.filter_buttons[mode_id] = btn

        # Scrollable Player Cards List
        self.scroll_players = ctk.CTkScrollableFrame(
            left_pane,
            corner_radius=8,
            fg_color=BG_CANVAS,
            border_width=1,
            border_color="#141E30",
        )
        self.scroll_players.grid(row=3, column=0, sticky="nsew", padx=10, pady=(2, 10))
        self.scroll_players.grid_columnconfigure(0, weight=1)

    def _build_right_editor_pane(self) -> None:
        right_pane = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_PANEL,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        right_pane.grid(row=1, column=1, sticky="nsew", padx=(6, 14), pady=(0, 8))
        right_pane.grid_columnconfigure(0, weight=1)
        right_pane.grid_rowconfigure(2, weight=1)

        # 1. Player Profile Header Card
        profile_card = ctk.CTkFrame(
            right_pane,
            corner_radius=8,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        profile_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        profile_card.grid_columnconfigure(0, weight=1)

        # Left Info Column
        info_col = ctk.CTkFrame(profile_card, fg_color="transparent")
        info_col.grid(row=0, column=0, sticky="nsew", padx=14, pady=10)

        self.lbl_player_name = ctk.CTkLabel(
            info_col,
            text="Select a Player",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_player_name.pack(anchor="w")

        self.lbl_player_sub = ctk.CTkLabel(
            info_col,
            text="Search by player name on the left to inspect and modify attributes",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_player_sub.pack(anchor="w", pady=(1, 4))

        self.lbl_memory_target = ctk.CTkLabel(
            info_col,
            text="Memory Target: Standby",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=ACCENT_CYAN,
        )
        self.lbl_memory_target.pack(anchor="w")

        # Right CA / PA / Reputation Controls
        capa_col = ctk.CTkFrame(profile_card, fg_color="#0D1422", corner_radius=8, border_width=1, border_color="#1D2B44")
        capa_col.grid(row=0, column=1, sticky="ns", padx=12, pady=10)

        # CA Control
        self._build_ability_spinner(capa_col, col=0, title="CURRENT ABILITY (CA)", max_val=200, attr_name="ca", color=ACCENT_CYAN)
        # PA Control
        self._build_ability_spinner(capa_col, col=1, title="POTENTIAL (PA)", max_val=200, attr_name="pa", color=ACCENT_VIOLET)
        # Reputation Control
        self._build_ability_spinner(capa_col, col=2, title="REPUTATION", max_val=10000, attr_name="rep", color=ACCENT_AMBER)

        # 2. One-Click Tactical Presets & Primary Write Bar
        preset_bar = ctk.CTkFrame(right_pane, fg_color="transparent")
        preset_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 6))

        presets = [
            ("SUPER BOOST (All 20s + 200)", "super_boost", ACCENT_ROSE, "#FFFFFF"),
            ("MAX CA/PA (200)", "max_capa", ACCENT_VIOLET, "#FFFFFF"),
            ("PEAK PHYSICAL + NO INJURY", "peak_physical", "#0284C7", "#FFFFFF"),
            ("CLINICAL FINISHER", "clinical_finisher", "#1E293B", TEXT_PRIMARY),
            ("PLAYMAKER MAESTRO", "playmaker_maestro", "#1E293B", TEXT_PRIMARY),
        ]
        for text, p_key, bg_c, txt_c in presets:
            btn = ctk.CTkButton(
                preset_bar,
                text=text,
                height=34,
                corner_radius=7,
                fg_color=bg_c,
                text_color=txt_c,
                hover_color="#334155" if bg_c == "#1E293B" else bg_c,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda k=p_key: self._on_apply_preset(k),
            )
            btn.pack(side="left", padx=(0, 6))

        self.btn_write_memory = ctk.CTkButton(
            preset_bar,
            text="WRITE TO FM26 MEMORY",
            height=34,
             width=185,
            corner_radius=7,
            fg_color=ACCENT_EMERALD,
            hover_color=ACCENT_EMERALD_HOVER,
            text_color="#021810",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._write_current_player_to_memory,
        )
        self.btn_write_memory.pack(side="right")

        # 3. Attribute & Telemetry Tabs
        self.tabs = ctk.CTkTabview(
            right_pane,
            corner_radius=8,
            fg_color=BG_CANVAS,
            segmented_button_fg_color="#0D1422",
            segmented_button_selected_color=ACCENT_EMERALD,
            segmented_button_selected_hover_color=ACCENT_EMERALD_HOVER,
            segmented_button_unselected_color="#0D1422",
            segmented_button_unselected_hover_color="#1A263B",
            text_color="#03140D",
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))

        self.tab_outfield = self.tabs.add("Outfield Attributes (Technical / Mental / Physical)")
        self.tab_gk_pos = self.tabs.add("Goalkeeping & Positions (15 Roles)")
        self.tab_memory = self.tabs.add("Live Memory & Audit Console")

        self._build_outfield_tab()
        self._build_gk_positions_tab()
        self._build_memory_console_tab()

    def _build_ability_spinner(
        self,
        parent: ctk.CTkFrame,
        col: int,
        title: str,
        max_val: int,
        attr_name: str,
        color: str,
    ) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, padx=10, pady=8)

        ctk.CTkLabel(
            box,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=TEXT_DIM,
        ).pack()

        entry = ctk.CTkEntry(
            box,
            width=76,
            height=30,
            justify="center",
            corner_radius=6,
            fg_color=BG_INPUT,
            border_color=color,
            text_color=color,
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
        )
        entry.pack(pady=(3, 2))
        entry.insert(0, str(max_val))
        entry.bind("<FocusOut>", lambda _e, a=attr_name: self._sync_header_entries(a))
        entry.bind("<Return>", lambda _e, a=attr_name: self._sync_header_entries(a))

        ctk.CTkLabel(
            box,
            text=f"Max {max_val}",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=TEXT_DIM,
        ).pack()

        if attr_name == "ca":
            self.entry_ca = entry
        elif attr_name == "pa":
            self.entry_pa = entry
        else:
            self.entry_rep = entry

    def _build_outfield_tab(self) -> None:
        self.tab_outfield.grid_columnconfigure(0, weight=1)
        self.tab_outfield.grid_columnconfigure(1, weight=1)
        self.tab_outfield.grid_columnconfigure(2, weight=1)
        self.tab_outfield.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.tab_outfield, fg_color="transparent")
        scroll.grid(row=0, column=0, columnspan=3, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)
        scroll.grid_columnconfigure(2, weight=1)

        # Column 0: Technical (14)
        col_tech = self._create_category_column(scroll, 0, "TECHNICAL", ACCENT_EMERALD)
        for attr in ATTRS_BY_CATEGORY["Technical"]:
            row = AttributeStepperRow(col_tech, attr, 15, self._on_attr_stepper_changed)
            row.pack(fill="x", padx=6, pady=2)
            self.attr_rows[attr.index] = row

        # Column 1: Mental (14)
        col_men = self._create_category_column(scroll, 1, "MENTAL", ACCENT_CYAN)
        for attr in ATTRS_BY_CATEGORY["Mental"]:
            row = AttributeStepperRow(col_men, attr, 15, self._on_attr_stepper_changed)
            row.pack(fill="x", padx=6, pady=2)
            self.attr_rows[attr.index] = row

        # Column 2: Physical (10) + Hidden (5)
        col_phys = self._create_category_column(scroll, 2, "PHYSICAL & HIDDEN (* Low=Best)", ACCENT_AMBER)
        for attr in ATTRS_BY_CATEGORY["Physical"] + ATTRS_BY_CATEGORY["Hidden"]:
            row = AttributeStepperRow(col_phys, attr, 15, self._on_attr_stepper_changed)
            row.pack(fill="x", padx=6, pady=2)
            self.attr_rows[attr.index] = row

    def _create_category_column(
        self,
        parent: ctk.CTkBaseClass,
        col_idx: int,
        title: str,
        accent_color: str,
    ) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color="#0B111D",
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        frame.grid(row=0, column=col_idx, sticky="nsew", padx=5, pady=4)

        hdr = ctk.CTkFrame(frame, fg_color="#121C2E", corner_radius=6, height=28)
        hdr.pack(fill="x", padx=6, pady=(6, 4))

        ctk.CTkLabel(
            hdr,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=accent_color,
        ).pack(side="left", padx=10, pady=4)

        return frame

    def _build_gk_positions_tab(self) -> None:
        self.tab_gk_pos.grid_columnconfigure(0, weight=1)
        self.tab_gk_pos.grid_columnconfigure(1, weight=1)
        self.tab_gk_pos.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.tab_gk_pos, fg_color="transparent")
        scroll.grid(row=0, column=0, columnspan=2, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        # Left Column: Goalkeeping (11)
        col_gk = self._create_category_column(scroll, 0, "GOALKEEPING ATTRIBUTES", ACCENT_VIOLET)
        for attr in ATTRS_BY_CATEGORY["Goalkeeping"]:
            row = AttributeStepperRow(col_gk, attr, 5, self._on_attr_stepper_changed)
            row.pack(fill="x", padx=6, pady=2)
            self.attr_rows[attr.index] = row

        # Right Column: 15 Positional Ratings (1-20)
        col_pos = self._create_category_column(
            scroll, 1, "POSITIONAL RATINGS (20 = Natural Role)", ACCENT_EMERALD
        )

        btn_all_pos = ctk.CTkButton(
            col_pos,
            text="Unlock All Outfield Positions to 20 (Natural)",
            height=28,
            corner_radius=6,
            fg_color="#1E293B",
            hover_color="#334155",
            text_color=ACCENT_EMERALD,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._unlock_all_positions,
        )
        btn_all_pos.pack(fill="x", padx=8, pady=(2, 6))

        pos_grid = ctk.CTkFrame(col_pos, fg_color="transparent")
        pos_grid.pack(fill="x", padx=6, pady=2)
        pos_grid.grid_columnconfigure(0, weight=1)
        pos_grid.grid_columnconfigure(1, weight=1)

        for idx, pdef in enumerate(POSITION_DEFS):
            r, c = divmod(idx, 2)
            cell = ctk.CTkFrame(pos_grid, fg_color="#0F1726", corner_radius=6, border_width=1, border_color="#19253B")
            cell.grid(row=r, column=c, sticky="ew", padx=4, pady=3)

            ctk.CTkLabel(
                cell,
                text=f"{pdef.code:4s} ({pdef.name})",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=TEXT_SECONDARY,
            ).pack(side="left", padx=8, pady=4)

            ent = ctk.CTkEntry(
                cell,
                width=44,
                height=24,
                justify="center",
                fg_color=BG_INPUT,
                border_color=BORDER_SUBTLE,
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            )
            ent.pack(side="right", padx=6, pady=4)
            ent.insert(0, "1")
            ent.bind("<FocusOut>", lambda _e, pi=pdef.index: self._on_pos_entry_changed(pi))
            ent.bind("<Return>", lambda _e, pi=pdef.index: self._on_pos_entry_changed(pi))
            self.pos_entries[pdef.index] = ent

    def _build_memory_console_tab(self) -> None:
        self.tab_memory.grid_columnconfigure(0, weight=1)
        self.tab_memory.grid_rowconfigure(1, weight=1)

        # Direct Memory & Target Inspector Bar
        top_card = ctk.CTkFrame(
            self.tab_memory,
            corner_radius=8,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        top_card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        row = ctk.CTkFrame(top_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            row,
            text="Raw Address:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left", padx=(0, 6))

        self.entry_raw_addr = ctk.CTkEntry(
            row,
            placeholder_text="0x7FF...",
            width=160,
            fg_color=BG_INPUT,
            border_color=BORDER_SUBTLE,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.entry_raw_addr.pack(side="left", padx=(0, 10))

        self.combo_raw_type = ctk.CTkComboBox(
            row,
            values=["1-Byte (uint8)", "2-Byte (uint16)", "4-Byte (uint32)"],
            width=145,
        )
        self.combo_raw_type.pack(side="left", padx=(0, 10))

        self.entry_raw_val = ctk.CTkEntry(
            row,
            placeholder_text="Value",
            width=95,
            fg_color=BG_INPUT,
            border_color=BORDER_SUBTLE,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.entry_raw_val.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Write Raw Address",
            width=140,
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._direct_memory_write,
        ).pack(side="left")

        ctk.CTkButton(
            row,
            text="Force Rescan Target in RAM",
            width=180,
            fg_color=ACCENT_CYAN,
            text_color="#04131F",
            hover_color="#0284C7",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self._resolve_and_sync_current_player(force_rescan=True),
        ).pack(side="right")

        # Audit Log Textbox
        self.log_textbox = ctk.CTkTextbox(
            self.tab_memory,
            corner_radius=8,
            fg_color="#05080E",
            border_width=1,
            border_color=BORDER_SUBTLE,
            text_color="#CBD5E1",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.log_textbox.configure(state="disabled")

    def _build_bottom_status_bar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            corner_radius=8,
            fg_color=BG_PANEL,
            border_width=1,
            border_color=BORDER_SUBTLE,
            height=32,
        )
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        self.lbl_status_bar = ctk.CTkLabel(
            bar,
            text="Ready. Search any player by name on the left.",
            anchor="w",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_status_bar.pack(side="left", padx=12, pady=4)

        ctk.CTkLabel(
            bar,
            text="Tip: Switch tabs or press Back/Forward in FM26 to refresh modified stats on screen.",
            anchor="e",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM,
        ).pack(side="right", padx=12, pady=4)

    # ------------------------------------------------------------------
    # SEARCH & PLAYER SELECTION
    # ------------------------------------------------------------------
    def _on_search_key_release(self, _event=None) -> None:
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(160, self._refresh_search_results)

    def _set_filter_mode(self, mode: str) -> None:
        self.filter_mode = mode
        for m_id, btn in self.filter_buttons.items():
            if m_id == mode:
                btn.configure(fg_color=ACCENT_CYAN, text_color="#04131F")
            else:
                btn.configure(fg_color="#1E293B", text_color=TEXT_SECONDARY)
        self._refresh_search_results()

    def _refresh_search_results(self) -> None:
        query = self.entry_search.get().strip()
        results = self.db.search_players(query, limit=35, filter_mode=self.filter_mode)

        for child in self.scroll_players.winfo_children():
            child.destroy()

        self.lbl_match_count.configure(
            text=f"{len(results)} / {self.db.player_count:,}"
        )

        if not results:
            ctk.CTkLabel(
                self.scroll_players,
                text="No matching players found.\nTry searching by surname or common name.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_DIM,
                justify="center",
            ).pack(pady=30)
            return

        selected_uid = self.current_player.uid if self.current_player else -1
        for p in results:
            card = PlayerResultCard(
                self.scroll_players,
                player=p,
                is_selected=(p.uid == selected_uid),
                on_select=self.select_player,
            )
            card.pack(fill="x", padx=2, pady=3)

    def select_player(self, player: PlayerRecord) -> None:
        self.current_player = player
        self.current_targets = []
        self._populate_player_editor(player)
        self._refresh_search_results()

        if self.fm_ctrl and self.fm_ctrl.is_alive():
            self._resolve_and_sync_current_player(force_rescan=False)
        else:
            self.lbl_memory_target.configure(
                text=f"Database Record Offset: 0x{max(0, player.db_offset):X}  |  Launch FM26 for Live Memory Hook",
                text_color=ACCENT_CYAN,
            )

    def _populate_player_editor(self, player: PlayerRecord) -> None:
        self.lbl_player_name.configure(text=player.display_name)
        pos_str = player.best_positions_str(4)
        self.lbl_player_sub.configure(
            text=f"{player.full_name}  |  Born {player.birth_year} (Age {player.age})  |  Roles: {pos_str}  |  UID: {player.uid}"
        )

        # Update CA, PA, Rep entries
        for entry, val in (
            (self.entry_ca, player.ca),
            (self.entry_pa, player.pa),
            (self.entry_rep, player.current_rep),
        ):
            entry.delete(0, "end")
            entry.insert(0, str(val))

        self.entry_ca.configure(text_color=get_ca_tier_color(player.ca))

        # Update all 54 attribute rows
        disp_attrs = player.get_display_attributes()
        for idx, row in self.attr_rows.items():
            row.set_value(disp_attrs.get(idx, 10), notify=False)

        # Update all 15 positional entries
        for idx, ent in self.pos_entries.items():
            val = player.positions[idx] if idx < len(player.positions) else 1
            ent.delete(0, "end")
            ent.insert(0, str(val))

    # ------------------------------------------------------------------
    # ATTRIBUTE, POSITION & PRESET EDITING
    # ------------------------------------------------------------------
    def _on_attr_stepper_changed(self, attr_idx: int, new_val_20: int) -> None:
        if not self.current_player:
            return
        self.current_player.set_display_attribute(attr_idx, new_val_20)

    def _on_pos_entry_changed(self, pos_idx: int) -> None:
        if not self.current_player or pos_idx not in self.pos_entries:
            return
        raw_txt = self.pos_entries[pos_idx].get().strip()
        if raw_txt.isdigit():
            val = max(1, min(20, int(raw_txt)))
            self.current_player.positions[pos_idx] = val
            self.pos_entries[pos_idx].delete(0, "end")
            self.pos_entries[pos_idx].insert(0, str(val))

    def _unlock_all_positions(self) -> None:
        if not self.current_player:
            return
        for idx in range(1, 15):
            self.current_player.positions[idx] = 20
        self._populate_player_editor(self.current_player)
        self.log(f"Unlocked all outfield positions to 20 (Natural) for {self.current_player.display_name}.", ACCENT_EMERALD)

    def _sync_header_entries(self, _field: str = "") -> None:
        if not self.current_player:
            return
        try:
            ca_v = max(1, min(200, int(self.entry_ca.get().strip())))
            pa_v = max(1, min(200, int(self.entry_pa.get().strip())))
            rep_v = max(1, min(10000, int(self.entry_rep.get().strip())))
            self.current_player.ca = ca_v
            self.current_player.pa = pa_v
            self.current_player.current_rep = rep_v
            self.current_player.world_rep = max(self.current_player.world_rep, rep_v)
            self._populate_player_editor(self.current_player)
        except ValueError:
            pass

    def _on_apply_preset(self, preset_key: str) -> None:
        if not self.current_player:
            self.log("Select a player first.", ACCENT_AMBER)
            return
        msg = apply_preset_to_player(self.current_player, preset_key)
        self._populate_player_editor(self.current_player)
        self._refresh_search_results()
        self.log(f"[{self.current_player.display_name}] {msg}", ACCENT_EMERALD)

        # If connected to FM26, immediately write to live memory
        if self.fm_ctrl and self.fm_ctrl.is_alive():
            self._write_current_player_to_memory()

    # ------------------------------------------------------------------
    # LIVE MEMORY RESOLUTION & WRITING
    # ------------------------------------------------------------------
    def _resolve_and_sync_current_player(self, force_rescan: bool = False) -> None:
        player = self.current_player
        if not player or not self.fm_ctrl or not self.fm_ctrl.is_alive():
            return

        self.lbl_memory_target.configure(
            text=f"Scanning FM26 memory for {player.display_name} (UID {player.uid})...",
            text_color=ACCENT_AMBER,
        )

        def _worker() -> None:
            t0 = time.time()
            targets = self.fm_ctrl.locate_player_targets(player, force_rescan=force_rescan)
            elapsed = time.time() - t0
            if targets:
                self.current_targets = targets
                self.fm_ctrl.sync_player_from_memory(player, targets)
                primary = targets[0]
                self._ui_call(lambda: self._populate_player_editor(player))
                self._ui_call(
                    lambda: self.lbl_memory_target.configure(
                        text=(
                            f"Locked {len(targets)} struct(s) in {elapsed:.2f}s  |  "
                            f"Base: 0x{primary.base_address:X} ({primary.layout})  |  "
                            f"CA: 0x{primary.ca_address:X}  |  Attrs: 0x{primary.attr_address:X}"
                        ),
                        text_color=ACCENT_EMERALD,
                    )
                )
                self.log(
                    f"Resolved {player.display_name} (UID {player.uid}) at 0x{primary.base_address:X} "
                    f"({len(targets)} instance(s) in {elapsed:.2f}s).",
                    ACCENT_EMERALD,
                )
            else:
                self._ui_call(
                    lambda: self.lbl_memory_target.configure(
                        text=f"UID {player.uid} not yet loaded in active FM26 view (Load save in FM26 first)",
                        text_color=ACCENT_AMBER,
                    )
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _write_current_player_to_memory(self) -> None:
        if not self.current_player:
            self.log("No player selected.", ACCENT_AMBER)
            return

        self._sync_header_entries()
        player = self.current_player

        if not self.fm_ctrl or not self.fm_ctrl.is_alive():
            self.probe_connection(quiet=True)

        if not self.fm_ctrl or not self.fm_ctrl.is_alive():
            self.log(
                f"Staged changes for {player.display_name} (CA={player.ca}, PA={player.pa}). "
                f"Launch Football Manager 26 (fm.exe) to write to live memory.",
                ACCENT_AMBER,
            )
            return

        self.btn_write_memory.configure(state="disabled", text="WRITING...")

        def _write_worker() -> None:
            try:
                targets = self.current_targets
                if not targets:
                    targets = self.fm_ctrl.locate_player_targets(player)
                    self.current_targets = targets

                if not targets:
                    self.log(
                        f"Could not find {player.display_name} (UID {player.uid}) in fm.exe memory. "
                        f"Make sure your save game is loaded inside FM26.",
                        ACCENT_ROSE,
                    )
                    return

                patched = self.fm_ctrl.write_player_stats(player, targets)
                if patched > 0:
                    primary = targets[0]
                    self.log(
                        f"Wrote stats for {player.display_name} (CA={player.ca}, PA={player.pa}, 1-100 scale) "
                        f"to {patched} live FM26 struct(s) at 0x{primary.base_address:X}!",
                        ACCENT_EMERALD,
                    )
                else:
                    self.log(
                        f"Memory write failed for {player.display_name}. Try running as Administrator.",
                        ACCENT_ROSE,
                    )
            finally:
                self._ui_call(
                    lambda: self.btn_write_memory.configure(
                        state="normal", text="WRITE TO FM26 MEMORY"
                    )
                )

        threading.Thread(target=_write_worker, daemon=True).start()

    def _direct_memory_write(self) -> None:
        if not self.fm_ctrl or not self.fm_ctrl.is_alive():
            self.log("Not connected to FM26 (fm.exe).", ACCENT_ROSE)
            return
        addr_str = self.entry_raw_addr.get().strip()
        val_str = self.entry_raw_val.get().strip()
        try:
            addr = int(addr_str, 16) if addr_str.lower().startswith("0x") else int(addr_str)
            val = int(val_str)
            dtype = self.combo_raw_type.get()
            if "1-Byte" in dtype:
                ok = self.fm_ctrl.write_uint8(addr, val)
            elif "2-Byte" in dtype:
                ok = self.fm_ctrl.write_uint16(addr, val)
            else:
                ok = self.fm_ctrl.write_uint32(addr, val)
            if ok:
                self.log(f"Wrote {val} ({dtype}) to 0x{addr:X}.", ACCENT_EMERALD)
            else:
                self.log(f"Failed to write to 0x{addr:X}.", ACCENT_ROSE)
        except Exception as exc:
            self.log(f"Direct write error: {exc}", ACCENT_ROSE)

    # ------------------------------------------------------------------
    # BACKGROUND SAVE INDEXER & PROCESS POLLER
    # ------------------------------------------------------------------
    def _start_background_services(self) -> None:
        threading.Thread(target=self._auto_index_latest_save, daemon=True).start()
        threading.Thread(target=self._process_poller, daemon=True).start()

    def _auto_index_latest_save(self) -> None:
        save_path = find_latest_fm26_save()
        if save_path:
            self._load_save_in_thread(save_path)

    def _browse_save_file(self) -> None:
        initial_dir = str(Path.home() / "Documents" / "Sports Interactive" / "Football Manager 26" / "games")
        path = filedialog.askopenfilename(
            title="Select Football Manager 26 Save File (.fm)",
            initialdir=initial_dir if Path(initial_dir).is_dir() else str(Path.home()),
            filetypes=[("FM26 Save Files", "*.fm"), ("All Files", "*.*")],
        )
        if path:
            threading.Thread(target=self._load_save_in_thread, args=(path,), daemon=True).start()

    def _load_save_in_thread(self, save_path: str) -> None:
        save_name = Path(save_path).name
        self._ui_call(
            lambda: self.lbl_db_badge.configure(
                text=f"Indexing {save_name}...", text_color=ACCENT_AMBER
            )
        )
        try:
            count = self.db.load_save_file(
                save_path,
                progress_cb=lambda msg: self.log(msg, ACCENT_CYAN),
            )
            self._ui_call(
                lambda: self.lbl_db_badge.configure(
                    text=f"DB: {count:,} Players ({save_name})",
                    text_color=ACCENT_EMERALD,
                )
            )
            self._ui_call(self._refresh_search_results)
            self.log(
                f"Indexed {count:,} players from '{save_name}' in {self.db.load_time_sec:.2f}s. "
                f"Name-only search ready!",
                ACCENT_EMERALD,
            )
        except Exception as exc:
            self.log(f"Save parse note ({save_name}): {exc}", ACCENT_AMBER)

    def _process_poller(self) -> None:
        while True:
            if not self.fm_ctrl or not self.fm_ctrl.is_alive():
                self.probe_connection(quiet=True)
            time.sleep(3.0)

    def probe_connection(self, quiet: bool = False) -> None:
        pid, name = get_fm_process()
        if pid and name:
            try:
                if self.fm_ctrl:
                    self.fm_ctrl.close()
                self.fm_ctrl = FMController(pid, name)
                self._ui_call(
                    lambda: self.lbl_proc_badge.configure(
                        text=f"LIVE: {name} (PID {pid})",
                        fg_color="#063322",
                        text_color=ACCENT_EMERALD,
                    )
                )
                if not quiet:
                    self.log(f"Attached to {name} (PID {pid}).", ACCENT_EMERALD)
            except Exception as exc:
                self._ui_call(
                    lambda: self.lbl_proc_badge.configure(
                        text="ACCESS DENIED (Run as Admin)",
                        fg_color="#310B15",
                        text_color=ACCENT_ROSE,
                    )
                )
                if not quiet:
                    self.log(f"Process attach error: {exc}", ACCENT_ROSE)
        else:
            if self.fm_ctrl:
                self.fm_ctrl.close()
                self.fm_ctrl = None
            self._ui_call(
                lambda: self.lbl_proc_badge.configure(
                    text="STANDBY: FM26 Not Running",
                    fg_color="#231B0A",
                    text_color=ACCENT_AMBER,
                )
            )
            if not quiet:
                self.log(
                    "FM26 (fm.exe) is not running yet. You can still search all players and stage edits.",
                    ACCENT_AMBER,
                )


if __name__ == "__main__":
    app = FM26TacticalModifierApp()
    app.mainloop()

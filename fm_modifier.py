"""
Football Manager 26 CLI Stat & Rating Trainer.

Supports instant Name-Only player lookup, full 54-attribute telemetry display,
and live memory patching from the terminal.
"""

import argparse
import sys
from typing import Optional

from fm_core import FMController, apply_preset_to_player, get_fm_process
from fm_database import FMDatabase, find_latest_fm26_save
from fm_schema import ATTRS_BY_CATEGORY, CATEGORIES, PlayerRecord


def print_player_card(player: PlayerRecord) -> None:
    disp_attrs = player.get_display_attributes()
    print("=" * 74)
    print(f"  {player.display_name.upper()}  |  UID: {player.uid}  |  Born: {player.birth_year} (Age {player.age})")
    print(f"  Full Name : {player.full_name}")
    print(f"  Positions : {player.best_positions_str(5)}")
    print(f"  Ability   : CA {player.ca} / 200   |   PA {player.pa} / 200   |   Rep {player.current_rep} / 10000")
    print("-" * 74)
    for cat in CATEGORIES:
        attrs = ATTRS_BY_CATEGORY[cat]
        parts = [f"{a.name}: {disp_attrs[a.index]:2d}" for a in attrs]
        print(f"  [{cat}]")
        for i in range(0, len(parts), 4):
            row = "   ".join(f"{p:22s}" for p in parts[i : i + 4])
            print(f"    {row}")
    print("=" * 74)


def run_cli(search_query: Optional[str] = None, preset: Optional[str] = None) -> int:
    db = FMDatabase()
    save_path = find_latest_fm26_save()
    if save_path:
        try:
            count = db.load_save_file(save_path)
            print(f"[DB] Indexed {count:,} players from save: {save_path}")
        except Exception as exc:
            print(f"[DB] Using built-in Star Catalog ({db.player_count} players). Note: {exc}")
    else:
        print(f"[DB] Using built-in Star Catalog ({db.player_count} players).")

    if search_query:
        matches = db.search_players(search_query, limit=10)
        if not matches:
            print(f"No players found matching '{search_query}'.")
            return 1
        print(f"\nFound {len(matches)} match(es) for '{search_query}':")
        for idx, p in enumerate(matches, 1):
            print(
                f"  [{idx:2d}] {p.display_name:26s} | UID {p.uid:10d} | "
                f"CA {p.ca:3d} / PA {p.pa:3d} | {p.best_positions_str()}"
            )
        target_player = matches[0]
        print("\nTop Match Telemetry:")
        print_player_card(target_player)

        if preset:
            msg = apply_preset_to_player(target_player, preset)
            print(f"\n[PRESET] {msg}")
            pid, proc_name = get_fm_process()
            if not pid:
                print("[MEMORY] FM26 (fm.exe) is not currently running. Launch FM26 to patch live memory.")
                return 0
            ctrl = FMController(pid, proc_name or "fm.exe")
            try:
                targets = ctrl.locate_player_targets(target_player)
                if not targets:
                    print(f"[MEMORY] Could not locate UID {target_player.uid} in {proc_name} memory.")
                    return 1
                patched = ctrl.write_player_stats(target_player, targets)
                print(f"[MEMORY] Patched {patched} live struct instance(s) in {proc_name} (PID {pid}).")
            finally:
                ctrl.close()
        return 0

    # Interactive loop
    print("\nFM26 Interactive Trainer (Type a player name to search, or 'q' to quit)")
    while True:
        try:
            q = input("\nSearch Player Name > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("q", "quit", "exit"):
            break
        matches = db.search_players(q, limit=8)
        if not matches:
            print("  No matching players found.")
            continue
        for idx, p in enumerate(matches, 1):
            print(
                f"  [{idx}] {p.display_name:25s} (UID {p.uid}) - CA {p.ca} / PA {p.pa} [{p.best_positions_str()}]"
            )
        print_player_card(matches[0])

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="FM26 Live Stat & Rating Modifier CLI")
    parser.add_argument("-s", "--search", help="Search player by name (e.g. 'Cristiano Ronaldo')")
    parser.add_argument(
        "-p",
        "--preset",
        choices=[
            "super_boost",
            "max_capa",
            "max_attributes",
            "peak_physical",
            "clinical_finisher",
            "playmaker_maestro",
        ],
        help="Optional preset to apply to the matched player",
    )
    args = parser.parse_args()
    sys.exit(run_cli(search_query=args.search, preset=args.preset))


if __name__ == "__main__":
    main()

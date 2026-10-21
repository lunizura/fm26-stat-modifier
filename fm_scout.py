"""
fm_scout.py - Tactical Scout Exporter & Player Comparison Engine for FM26
Provides JSON/CSV data export and attribute-by-attribute player comparison matrices.
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from fm_schema import ATTRIBUTE_DEFS, to_display_attr


def export_player_json(player: Dict[str, Any], filepath: str | Path) -> str:
    """Export single player profile to formatted JSON."""
    out = Path(filepath)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(player, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out)


def export_roster_csv(players: List[Dict[str, Any]], filepath: str | Path) -> str:
    """Export multiple player profiles to standard scout CSV spreadsheet."""
    out = Path(filepath)
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "uid", "name", "nation", "club", "age", "ca", "pa",
        "Pace", "Acceleration", "Finishing", "Passing", "Dribbling",
        "Tackling", "Determination", "Composure", "Work Rate", "Stamina"
    ]

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in players:
            row = {
                "uid": p.get("uid", ""),
                "name": p.get("name", ""),
                "nation": p.get("nation", ""),
                "club": p.get("club", ""),
                "age": p.get("age", ""),
                "ca": p.get("ca", ""),
                "pa": p.get("pa", ""),
            }
            attrs = p.get("attributes", {})
            for attr_name in fieldnames[7:]:
                val = attrs.get(attr_name, "")
                row[attr_name] = val
            writer.writerow(row)

    return str(out)


def compare_players(player_a: Dict[str, Any], player_b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two player profiles across technical, mental, and physical attributes."""
    attrs_a = player_a.get("attributes", {})
    attrs_b = player_b.get("attributes", {})

    diffs: Dict[str, Dict[str, Any]] = {}
    wins_a = 0
    wins_b = 0
    ties = 0

    all_keys = set(attrs_a.keys()).union(set(attrs_b.keys()))
    for key in sorted(all_keys):
        va = attrs_a.get(key, 0)
        vb = attrs_b.get(key, 0)
        delta = va - vb
        if delta > 0:
            wins_a += 1
            advantage = player_a.get("name", "Player A")
        elif delta < 0:
            wins_b += 1
            advantage = player_b.get("name", "Player B")
        else:
            ties += 1
            advantage = "Tie"

        diffs[key] = {
            "player_a": va,
            "player_b": vb,
            "delta": delta,
            "advantage": advantage
        }

    return {
        "player_a_name": player_a.get("name", "Player A"),
        "player_b_name": player_b.get("name", "Player B"),
        "total_attributes_compared": len(diffs),
        "player_a_wins": wins_a,
        "player_b_wins": wins_b,
        "ties": ties,
        "overall_winner": player_a.get("name", "Player A") if wins_a > wins_b else (player_b.get("name", "Player B") if wins_b > wins_a else "Tie"),
        "attribute_matrix": diffs
    }

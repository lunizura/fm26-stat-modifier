"""
Standalone PyInstaller Build Script for FM26 Tactical Scout & Stat Modifier.

Compiles `app_gui.py` into a single-file Windows GUI executable (`FM26_Stat_Modifier.exe`)
bundling CustomTkinter assets and Zstandard native bindings.
"""

from pathlib import Path
import shutil
import subprocess
import sys


def build_standalone_exe(copy_to_desktop: bool = True) -> Path:
    project_dir = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "FM26_Stat_Modifier",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "zstandard",
        str(project_dir / "app_gui.py"),
    ]
    print("Running PyInstaller:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(project_dir), check=True)

    dist_exe = project_dir / "dist" / "FM26_Stat_Modifier.exe"
    if not dist_exe.is_file():
        raise FileNotFoundError(f"Expected executable not found at {dist_exe}")

    print(f"Built standalone executable: {dist_exe} ({dist_exe.stat().st_size:,} bytes)")

    if copy_to_desktop:
        desktop_dir = Path.home() / "Desktop"
        if desktop_dir.is_dir():
            target = desktop_dir / "FM26_Stat_Modifier.exe"
            shutil.copy2(dist_exe, target)
            print(f"Updated Desktop executable: {target}")

    return dist_exe


if __name__ == "__main__":
    build_standalone_exe()

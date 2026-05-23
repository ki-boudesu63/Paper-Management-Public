"""Standalone folder picker script using tkinter.

Runs as a subprocess to isolate the GUI from the uvicorn server process.
Prints the selected folder path to stdout, or an empty string on cancel.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import filedialog


def main() -> None:
    """Open a native folder selection dialog and print the result."""
    root = tk.Tk()
    root.withdraw()
    # Bring the dialog to the front on Windows: keep the (hidden) root
    # topmost and pass it as the dialog parent so the native file dialog
    # inherits foreground activation instead of opening behind other windows.
    root.attributes("-topmost", True)
    root.update()

    initial_dir = sys.argv[1] if len(sys.argv) > 1 else ""

    selected = filedialog.askdirectory(
        parent=root,
        title="フォルダを選択",
        initialdir=initial_dir if initial_dir else None,
    )

    root.destroy()

    # Print the selected path (empty string if cancelled)
    print(selected or "")


if __name__ == "__main__":
    main()

"""Position native dialogs in physical screen coordinates, respecting CTk scaling."""

from __future__ import annotations

import sys
from typing import Any


def work_area(parent: Any) -> tuple[int, int, int, int]:
    """Return the work area of the parent's monitor (including negative origins)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("monitor", wintypes.RECT),
                ("work", wintypes.RECT),
                ("flags", wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        monitor = user32.MonitorFromWindow(parent.winfo_id(), 2)
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    return 0, 0, parent.winfo_screenwidth(), parent.winfo_screenheight()


def centered_bounds(
    parent_bounds: tuple[int, int, int, int],
    size: tuple[int, int],
    area: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Center within the owning window and keep the dialog inside its monitor."""
    px, py, pw, ph = parent_bounds
    left, top, right, bottom = area
    width, height = min(size[0], right - left - 24), min(size[1], bottom - top - 48)
    x = max(left + 12, min(px + (pw - width) // 2, right - width - 12))
    y = max(top + 32, min(py + (ph - height) // 2, bottom - height - 16))
    return width, height, x, y


def center_dialog(dialog: Any, parent: Any, *, width: int, min_height: int = 0) -> None:
    """Use the root window, rather than an inner content frame, as the owner.

    CTk geometry sizes are logical pixels, but Tk root positions and requested
    sizes are physical pixels. Passing a physical width back to CTk scales it
    twice on Windows, so convert sizes only; geometry offsets stay physical.
    """
    owner = parent.winfo_toplevel()
    dialog.update_idletasks()
    if not dialog.winfo_ismapped() and not getattr(dialog, "_centering_map_id", None):

        def on_map(event: Any) -> None:
            if event.widget is dialog:
                dialog.unbind("<Map>", dialog._centering_map_id)
                dialog._centering_map_id = None
                dialog.after_idle(
                    lambda: center_dialog(
                        dialog, parent, width=width, min_height=min_height
                    )
                )

        dialog._centering_map_id = dialog.bind("<Map>", on_map, add="+")
    scale = dialog._get_window_scaling()
    requested = (
        round(width * scale),
        max(dialog.winfo_reqheight(), round(min_height * scale)),
    )
    bounds = (
        owner.winfo_rootx(),
        owner.winfo_rooty(),
        owner.winfo_width(),
        owner.winfo_height(),
    )
    w, h, x, y = centered_bounds(bounds, requested, work_area(owner))
    # geometry offsets address the native outer frame, while rootx/rooty
    # address the client area. Account for the title bar and invisible borders.
    _, _, frame_x, frame_y = dialog._parse_geometry_string(dialog.geometry())
    native_offset = None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        handle = user32.GetAncestor(dialog.winfo_id(), 2)
        outer, client = wintypes.RECT(), wintypes.POINT(0, 0)
        if (
            handle
            and user32.GetWindowRect(handle, ctypes.byref(outer))
            and user32.ClientToScreen(handle, ctypes.byref(client))
        ):
            # Native chrome already has a size while CTk briefly withdraws the
            # window to apply its title bar; winfo_ismapped is false then.
            native_offset = client.x - outer.left, client.y - outer.top
    if native_offset is not None:
        x -= native_offset[0]
        y -= native_offset[1]
    elif dialog.winfo_ismapped() and frame_x is not None and frame_y is not None:
        x -= dialog.winfo_rootx() - frame_x
        y -= dialog.winfo_rooty() - frame_y
    # '+-x' is intentional: Tk interprets '-x' as an offset from the right edge.
    dialog.geometry(f"{round(w / scale)}x{round(h / scale)}+{x}+{y}")

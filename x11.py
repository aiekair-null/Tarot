"""Window placement on X11, talking to the display directly through python-xlib -- no wmctrl, no xdotool,
nothing that has to come from pacman (or any system package manager at all). python-xlib is pure Python and
installs with a plain `pip install python-xlib`; deps.ensure_python() offers to do that the first time it's
needed and nothing else in this module ever touches pacman.

This speaks the same EWMH window-manager protocol wmctrl itself speaks under the hood (_NET_CLIENT_LIST to
find windows, _NET_MOVERESIZE_WINDOW to move/resize them, _NET_ACTIVE_WINDOW to focus one, _NET_WM_STATE to
maximize), so it works with any EWMH-compliant window manager (i3, sway's Xwayland, bspwm, openbox, xfwm4,
KDE, GNOME's Xorg session, and more)."""
import os

import deps

_disp = None
_atoms = {}


def _connect():
    """The shared Xlib Display connection, opened once and reused. None if python-xlib isn't installed, or
    there's no X server to talk to (no DISPLAY, Wayland-only session, SSH with no X forwarding, etc.)."""
    global _disp
    if _disp is not None:
        return _disp
    try:
        from Xlib import display
        _disp = display.Display()
    except Exception:
        return None
    return _disp


def _atom(name):
    d = _connect()
    if name not in _atoms:
        _atoms[name] = d.intern_atom(name)
    return _atoms[name]


def ensure(ask=None, say=None, why="Placing her windows into a grid"):
    """Make sure python-xlib is importable and a display is reachable, offering a plain `pip install` (never
    pacman) if it's missing. Returns "" on success, or a short reason it can't be used, so callers can tell
    you instead of silently doing nothing."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no desktop session"
    if not deps.has_module("Xlib"):
        if not deps.ensure_python({"Xlib": "python-xlib"}, ask or deps.default_ask, say or deps.default_say, why):
            return "python-xlib isn't installed (pip install python-xlib -- no pacman needed)"
    if _connect() is None:
        return "couldn't connect to the X display"
    return ""


def available():
    return _connect() is not None


def display_size():
    """(width, height) of the screen in pixels, or None."""
    d = _connect()
    if d is None:
        return None
    try:
        screen = d.screen()
        return screen.width_in_pixels, screen.height_in_pixels
    except Exception:
        return None


def _client_windows():
    """Every top-level window the window manager is currently managing, via _NET_CLIENT_LIST on the root."""
    d = _connect()
    if d is None:
        return []
    try:
        prop = d.screen().root.get_full_property(_atom("_NET_CLIENT_LIST"), 0)
        return list(prop.value) if prop and prop.value is not None else []
    except Exception:
        return []


def _window_title(win):
    try:
        prop = win.get_full_property(_atom("_NET_WM_NAME"), 0)
        if prop and prop.value:
            v = prop.value
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
    except Exception:
        pass
    try:
        name = win.get_wm_name()
        return name or ""
    except Exception:
        return ""


def _find(title):
    """The (raw Xlib) window object whose title contains `title` -- the most recently created one wins if
    there's more than one, same as wmctrl/xdotool picking up a fresh window with a reused title -- or None."""
    d = _connect()
    if d is None:
        return None
    hit = None
    for wid in _client_windows():
        try:
            win = d.create_resource_object("window", wid)
            if title in _window_title(win):
                hit = win
        except Exception:
            continue
    return hit


def _absolute_pos(win):
    """(x, y) of a window's own origin in root/screen coordinates. get_geometry() only gives a window's
    position relative to its immediate parent (usually a decoration frame the window manager reparented it
    into, not the root), so this walks up the parent chain, summing each ancestor's own offset, until it
    reaches a direct child of the root window."""
    d = _connect()
    root = d.screen().root
    geom = win.get_geometry()
    x, y = geom.x, geom.y
    parent = win.query_tree().parent
    while parent is not None and parent.id != root.id:
        pgeom = parent.get_geometry()
        x += pgeom.x
        y += pgeom.y
        parent = parent.query_tree().parent
    return x, y


def find_window(title):
    """(x, y, w, h) in screen coordinates of the window whose title contains `title`, or None if there's no
    such window (yet), python-xlib isn't available, or there's no display to ask."""
    d = _connect()
    win = _find(title)
    if d is None or win is None:
        return None
    try:
        geom = win.get_geometry()
        x, y = _absolute_pos(win)
        return x, y, geom.width, geom.height
    except Exception:
        return None


def _moveresize_message(win, x, y, w, h):
    """A _NET_MOVERESIZE_WINDOW client message to the root window -- the same EWMH request wmctrl's -e sends,
    so the window manager (not us) actually performs the move/resize, respecting its own constraints."""
    from Xlib import X
    from Xlib.protocol import event
    d = _connect()
    STATIC_GRAVITY = 10
    SOURCE_APPLICATION = 1
    flags = STATIC_GRAVITY | (0xF << 8) | (SOURCE_APPLICATION << 12)
    ev = event.ClientMessage(window=win, client_type=_atom("_NET_MOVERESIZE_WINDOW"),
                              data=(32, [flags, x, y, w, h]))
    mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
    d.screen().root.send_event(ev, event_mask=mask)
    d.flush()


def place(title, x, y, w, h):
    """Move and resize the window with this title. Returns True if a matching window was found and asked to
    move (the window manager may still clamp or ignore parts of the request, same as wmctrl)."""
    d = _connect()
    win = _find(title)
    if d is None or win is None:
        return False
    try:
        _moveresize_message(win, x, y, w, h)
        return True
    except Exception:
        pass
    try:                                                   # fallback for a bare X session with no WM at all
        win.configure(x=x, y=y, width=w, height=h)
        d.flush()
        return True
    except Exception:
        return False


def focus(title):
    """Raise and give keyboard focus to the window with this title, via _NET_ACTIVE_WINDOW."""
    from Xlib import X
    from Xlib.protocol import event
    d = _connect()
    win = _find(title)
    if d is None or win is None:
        return False
    try:
        ev = event.ClientMessage(window=win, client_type=_atom("_NET_ACTIVE_WINDOW"),
                                  data=(32, [1, X.CurrentTime, 0, 0, 0]))
        mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
        d.screen().root.send_event(ev, event_mask=mask)
        d.flush()
        return True
    except Exception:
        return False


def maximize_active():
    """Ask the window manager to maximize whichever window is currently focused, via _NET_WM_STATE."""
    from Xlib import X
    from Xlib.protocol import event
    d = _connect()
    if d is None:
        return False
    try:
        prop = d.screen().root.get_full_property(_atom("_NET_ACTIVE_WINDOW"), 0)
        ids = list(prop.value) if prop and prop.value is not None else []
        if not ids:
            return False
        win = d.create_resource_object("window", ids[0])
        ADD = 1
        ev = event.ClientMessage(window=win, client_type=_atom("_NET_WM_STATE"),
                                  data=(32, [ADD, _atom("_NET_WM_STATE_MAXIMIZED_VERT"),
                                             _atom("_NET_WM_STATE_MAXIMIZED_HORZ"), 1, 0]))
        mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
        d.screen().root.send_event(ev, event_mask=mask)
        d.flush()
        return True
    except Exception:
        return False

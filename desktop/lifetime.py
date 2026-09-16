"""Observe an owner pipe without holding a blocking CRT input lock on Windows."""
import os
import sys
import time


def wait_for_owner():
    fd = sys.stdin.fileno()
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD]
        peek.restype = wintypes.BOOL
        handle = msvcrt.get_osfhandle(fd)
        while peek(handle, None, 0, None, None, None):
            time.sleep(.25)
        return
    import select
    while True:
        readable, _, _ = select.select([fd], [], [], 1)
        if readable and not os.read(fd, 1024):
            return

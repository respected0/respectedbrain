"""Operating-system adapters, invoked explicitly rather than at import time."""
from __future__ import annotations

from pathlib import Path
import os
from uuid import UUID


def known_folder(name: str) -> Path:
    """Read Windows Known Folders, including redirected Documents.

    IDs: https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
    """
    if os.name != "nt":
        raise OSError("Windows Known Folders are unavailable on this platform")
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD),
                    ("data3", wintypes.WORD), ("data4", ctypes.c_ubyte * 8)]

    ids = {"LocalAppData": "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",
           "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7"}
    guid = GUID.from_buffer_copy(UUID(ids[name]).bytes_le)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    read = shell.SHGetKnownFolderPath
    read.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    read.restype = ctypes.c_long
    result = ctypes.c_wchar_p()
    status = read(ctypes.byref(guid), 0, None, ctypes.byref(result))
    if status != 0:
        raise OSError(f"Known Folder {name} failed: HRESULT {status & 0xffffffff:08x}")
    free = ctypes.WinDLL("ole32").CoTaskMemFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    try:
        return Path(result.value)
    finally:
        free(ctypes.cast(result, ctypes.c_void_p))

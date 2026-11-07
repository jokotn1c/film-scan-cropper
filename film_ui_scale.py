"""Typography and uniform sizing for the macOS preview interface."""
import ctypes
import sys
from pathlib import Path

BASE_WIDTH, BASE_HEIGHT = 1440, 900


def layout_scale(width, height):
    return max(.5, min(float(width) / BASE_WIDTH, float(height) / BASE_HEIGHT))


def choose_latin_font(families):
    for name in ('EB Garamond', 'Garamond', 'Georgia', 'Times'):
        if name in families:
            return name
    return 'TkDefaultFont'


def choose_chinese_font(families):
    for name in ('Songti SC', 'STSong', 'Songti TC', 'Songti SC Regular', 'Georgia'):
        if name in families:
            return name
    return 'TkDefaultFont'


def register_bundled_font():
    if sys.platform != 'darwin':
        return
    font_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'EBGaramond.ttf'
    if not font_path.exists():
        return
    cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    ct = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    url = cf.CFURLCreateFromFileSystemRepresentation(None, bytes(font_path), len(bytes(font_path)), False)
    if url:
        try:
            ct.CTFontManagerRegisterFontsForURL(url, 1, None)
        finally:
            cf.CFRelease(url)

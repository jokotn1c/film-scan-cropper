"""Typography and uniform sizing for the preview interface."""
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
    # Tk exposes localized family names on some Windows installations.
    for name in ('Microsoft YaHei UI', 'Microsoft YaHei', '微软雅黑 UI', '微软雅黑',
                 'PingFang SC', '苹方-简', 'Heiti SC', '黑体-简', 'STHeiti',
                 'SimHei', '黑体', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei'):
        if name in families:
            return name
    return 'TkDefaultFont'


def register_bundled_font():
    font_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'EBGaramond.ttf'
    if not font_path.exists():
        return
    if sys.platform == 'win32':
        register = ctypes.WinDLL('gdi32', use_last_error=True).AddFontResourceExW
        register.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        register.restype = ctypes.c_int
        register(str(font_path), 0x10, None)  # FR_PRIVATE: this process only.
        return
    if sys.platform != 'darwin':
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

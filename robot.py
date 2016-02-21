import os
import ctypes
from ctypes import wintypes
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)

# input types
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# keyboard events
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MAPVK_VK_TO_VSC = 0

# mouse events
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

WHEEL_DELTA = 120

# virtual keycodes
keys = {
    'VK_SHIFT': 0x10,
    'VK_CONTROL': 0x11,
    'VK_LSHIFT': 0xA0,
    'VK_RSHIFT': 0xA1,
    'VK_LCONTRTOL': 0xA2,
    'VK_RCONTROL': 0xA3,
    'VK_SPACE': 0x20,
    'VK_MENU': 0x12,
    'VK_ESCAPE': 0x1B
}
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTRTOL = 0xA2
VK_RCONTROL = 0xA3
VK_SPACE = 0x20

# I'm not really sure if this is 100% correct/smart
# the MSDN docs define it as:
#   typedef UINT_PTR WPARAM;
# which appears to be different on a 32bit platform from ULONG_PTR:
#   typedef unsigned int UINT_PTR; vs typedef unsigned long ULONG_PTR
# but the same on 64, they are both __int64...
wintypes.ULONG_PTR = wintypes.WPARAM

class MOUSEINPUT(ctypes.Structure):
    _fields_ = (("dx",          wintypes.LONG),
                ("dy",          wintypes.LONG),
                ("mouseData",   wintypes.DWORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk",         wintypes.WORD),
                ("wScan",       wintypes.WORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))
    def __init__(self, *args, **kwds):
        super(KEYBDINPUT, self).__init__(*args, **kwds)
        # some programs use the scan code even if KEYEVENTF_SCANCODE
        # isn't set in dwFflags, so attempt to map the correct code.
        if not self.dwFlags & KEYEVENTF_UNICODE:
            self.wScan = user32.MapVirtualKeyExW(self.wVk,
                                                 MAPVK_VK_TO_VSC, 0)

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg",    wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD))

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT))
    _anonymous_ = ("_input",)
    _fields_ = (("type",   wintypes.DWORD),
                ("_input", _INPUT))

def _check_count(result, func, args):
    if result == 0:
        # result will be the number of events pushed; 0 implies it failed
        raise ctypes.WinError(ctypes.get_last_error())
    return args

user32.SendInput.errcheck = _check_count
user32.SendInput.argtypes = (wintypes.UINT,         # nInputs
                             ctypes.POINTER(INPUT), # pInputs
                             ctypes.c_int)          # cbSize

def _check_success(result, func, args):
    if result == 0xFFFF:
        # high and low order bits will be -1 (0xFF) on failure
        raise ctypes.WinError(ctypes.get_last_error())
    return result

# should really use VkKeyScanEx, but that's a little more involved
# so for now let's use this
user32.VkKeyScanA.errcheck = _check_success
user32.VkKeyScanA.argtypes = (wintypes.WCHAR,) # ch
user32.VkKeyScanA.restype = ctypes.c_ushort

def getKeyFromAscii(k):
    return user32.VkKeyScanA(k) & 0xFF
    
def pressKey(hexKeyCode):
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=hexKeyCode))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def releaseKey(hexKeyCode):
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=hexKeyCode,
                            dwFlags=KEYEVENTF_KEYUP))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def translateMouse(dx, dy):
    dx, dy = int(dx), int(dy)
    """ Translate mouse in pixels """
    x = INPUT(type=INPUT_MOUSE,
              mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=0,
                            dwFlags=MOUSEEVENTF_MOVE,
                            time=0, dwExtraInfo=0))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def placeMouse(x, y):
    """ Place mouse at (x, y), on range [0, 65535] """
    i = INPUT(type=INPUT_MOUSE,
              mi=MOUSEINPUT(dx=x, dy=y, mouseData=0,
                            dwFlags=MOUSEEVENTF_ABSOLUTE,
                            time=0, dwExtraInfo=0))
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))

def scrollWheel(y=0, x=0):
    """ Scroll the wheel in terms of wheel clicks """
    x = int(x * WHEEL_DELTA)
    y = int(y * WHEEL_DELTA)
    if x != 0 and y != 0:
        i = INPUT(type=INPUT_MOUSE,
                  mi=MOUSEINPUT(dx=0, dy=0, mouseData=x,
                                dwFlags=MOUSEEVENTF_HWHEEL,
                                time=0, dwExtraInfo=0))
        user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
        i.mi.mouseData = y
        i.mi.dwFlags = MOUSEEVENTF_WHEEL
        user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
        return

    if x != 0:
        # horizontal scroll
        i = INPUT(type=INPUT_MOUSE,
                  mi=MOUSEINPUT(dx=0, dy=0, mouseData=x,
                                dwFlags=MOUSEEVENTF_HWHEEL,
                                time=0, dwExtraInfo=0))
    else:
        # vertical scroll
        i = INPUT(type=INPUT_MOUSE,
                  mi=MOUSEINPUT(dx=0, dy=0, mouseData=y,
                                dwFlags=MOUSEEVENTF_WHEEL,
                                time=0, dwExtraInfo=0))

    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
    
def mouseButton(mouseEventMask):
    i = INPUT(type=INPUT_MOUSE,
              mi=MOUSEINPUT(dx=0, dy=0, mouseData=0,
                            dwFlags=mouseEventMask,
                            time=0, dwExtraInfo=0))
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))

def altTabTest():
    """Press Alt+Tab and hold Alt key for 2 seconds
    in order to see the overlay.
    """
    # msdn.microsoft.com/en-us/library/dd375731
    VK_TAB  = 0x09
    VK_MENU = 0x12 # Alt key
    pressKey(VK_MENU)   # Alt
    pressKey(VK_TAB)    # Tab
    releaseKey(VK_TAB)  # Tab~
    time.sleep(2)
    releaseKey(VK_MENU) # Alt~
    
def keyboardTest():
    print("Modifier:", hex((user32.VkKeyScanA("!") & 0xFF00) >> 8),
          "Key:", hex(user32.VkKeyScanA("9") & 0xFF))
          
    # move the mouse to the left
    translateMouse(-20, 0)
    # move the mouse up
    translateMouse(0, -10)
    scrollWheel(1)

if __name__ == "__main__":
    keyboardTest()
import ctypes
from ctypes import wintypes
import os
import time

xinput = ctypes.WinDLL('xinput1_3', use_last_error=True)

def poll(id):
    state = XINPUT_STATE()
    ctypes.memset(ctypes.addressof(state), 0, ctypes.sizeof(state))
    xinput.XInputGetState(id, ctypes.byref(state))
    return xinput_dict(state.gamepad)

def xinput_dict(struct):
    r = dict((i[0], getattr(struct, i[0])) for i in struct._fields_)
    r['buttons'] = list(bitmask_iter(r['buttons'], 16))
    return r

ERROR_SUCCESS = 0x0000
ERROR_DEVICE_NOT_CONNECTED = 0x048F

class NoControllerError(Exception):
    def __init__(self, message):
        super(NoControllerError, self).__init__(message)

class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = (('buttons',         ctypes.c_ushort),  # wButtons
                ('left_trigger',    ctypes.c_ubyte),  # bLeftTrigger
                ('right_trigger',   ctypes.c_ubyte),  # bLeftTrigger
                ('l_thumb_x',       ctypes.c_short),  # sThumbLX
                ('l_thumb_y',       ctypes.c_short),  # sThumbLY
                ('r_thumb_x',       ctypes.c_short),  # sThumbRx
                ('r_thumb_y',       ctypes.c_short))  # sThumbRy
    
class XINPUT_STATE(ctypes.Structure):
    _fields_ = (('packet_number', wintypes.DWORD),  # dwPacketNumber
                ('gamepad',       XINPUT_GAMEPAD))  # Gamepad

class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = (('left_motor_speed', wintypes.DWORD),
                ('right_motor_speed', wintypes.DWORD))

def _check_success(result, func, args):
    if result == ERROR_DEVICE_NOT_CONNECTED:
        raise NoControllerError("Controller " + str(args[0])
                              + " is not connected")

    if result != ERROR_SUCCESS:
        raise ctypes.WinError(ctypes.get_last_error())

    return args

xinput.XInputGetState.errcheck = _check_success
xinput.XInputGetState.args = (wintypes.DWORD,
                              ctypes.POINTER(XINPUT_STATE))
xinput.XInputSetState.errcheck = _check_success
xinput.XInputSetState.args = (wintypes.DWORD,
                              ctypes.POINTER(XINPUT_VIBRATION))

def bitmask_iter(mask, length):
    """ turn mask into list of the bits, least significant bit at index 0 """
    i = length
    while i:
        yield mask & 0x01
        mask >>= 1
        i -= 1

def controllerTest():
    state = XINPUT_STATE()
    ctypes.memset(ctypes.addressof(state), 0, ctypes.sizeof(state))
    xinput.XInputGetState(0, ctypes.byref(state))
    original = state.packet_number
    print('Press a button (or not...):')
    time.sleep(2)
    ctypes.memset(ctypes.addressof(state), 0, ctypes.sizeof(state))
    xinput.XInputGetState(0, ctypes.byref(state))
    if state.packet_number != original:
        print('You did something!')
    else:
        print('You did not press anything!')
        # vibrate the controller for two seconds
        vib = XINPUT_VIBRATION(right_motor_speed=0, left_motor_speed=10000)
        xinput.XInputSetState(0, ctypes.byref(vib))
        time.sleep(2)
        vib.left_motor_speed = 0
        xinput.XInputSetState(0, ctypes.byref(vib))

    gamepad = state.gamepad
    print('Analog:', gamepad.r_thumb_x)
    print('Buttons:', list(bitmask_iter(gamepad.buttons, 16)))
    print('Triggers', gamepad.left_trigger, gamepad.right_trigger)

def controllerDebug():
    while True:
        state = XINPUT_STATE()
        ctypes.memset(ctypes.addressof(state), 0, ctypes.sizeof(state))
        xinput.XInputGetState(0, ctypes.byref(state))
        gamepad = state.gamepad
        print("Hit Ctrl-C to exit.")
        print('Buttons:', list(bitmask_iter(gamepad.buttons, 16)))
        print('Right Stick:', (gamepad.r_thumb_x, gamepad.r_thumb_y))
        print('Left Stick:', (gamepad.l_thumb_x, gamepad.l_thumb_y))
        print('Triggers', gamepad.left_trigger, gamepad.right_trigger)
        time.sleep(1)
        os.system('CLS')
        
if __name__ == "__main__":
    controllerDebug()
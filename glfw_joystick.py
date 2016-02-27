import ctypes

glfw = ctypes.WinDLL("lib/glfw3.dll")
glfw.glfwInit()

def poll(id):
    return {
        'buttons': glfw.glfwGetJoystickButtons(id,
                                               ctypes.byref(ctypes.c_int(0))),
        'axes': glfw.glfwGetJoystickAxes(id, ctypes.byref(ctypes.c_int(0)))
    }

GLFW_JOYSTICK_1 = 0
GLFW_JOYSTICK_LAST = 15

GLFW_PRESS = 1
GLFW_RELEASE = 0

glfw.glfwJoystickPresent.args = (ctypes.c_int, )
glfw.glfwJoystickPresent.restype = ctypes.c_int

glfw.glfwGetJoystickAxes.args = (ctypes.c_int, ctypes.POINTER(ctypes.c_int))
glfw.glfwGetJoystickAxes.restype = ctypes.POINTER(ctypes.c_float)
def axisArray(res, func, args):
    controller, count = args
    count = ctypes.cast(count, ctypes.POINTER(ctypes.c_int)).contents.value
    if not res:
        raise ValueError("Controller " + str(controller) + " is not connected.")
    # convert pointer to array to list of float
    out = []
    for i in range(count):
        out.append(res[i])

    return out
glfw.glfwGetJoystickAxes.errcheck = axisArray

glfw.glfwGetJoystickButtons.args = (ctypes.c_int, ctypes.POINTER(ctypes.c_int))
glfw.glfwGetJoystickButtons.restype = ctypes.POINTER(ctypes.c_ubyte)
def buttonArray(res, func, args):
    controller, count = args
    count = ctypes.cast(count, ctypes.POINTER(ctypes.c_int)).contents.value
    if not res:
        raise ValueError("Controller " + str(controller) + " is not connected.")
    # convert pointer to array to list of int
    out = []
    for i in range(count):
        out.append(res[i])

    return out

glfw.glfwGetJoystickButtons.errcheck = buttonArray

glfw.glfwGetJoystickName.args = (ctypes.c_int, )
glfw.glfwGetJoystickName.restype = ctypes.c_char_p
def nameCheck(res, func, args):
    if not res:
        raise ValueError("Controller " + str(args[0]) + " is not connected.")
    return res.decode('utf-8')

glfw.glfwGetJoystickName.errcheck = nameCheck

def buttonTest(breakOnPress=False):
    while True:
        buttons = glfw.glfwGetJoystickButtons(0, ctypes.byref(ctypes.c_int(0)))
        if 1 in buttons:
            print('You pressed button', buttons.index(1))
            if breakOnPress:
                break

def axisTest():
    while True:
        axes = glfw.glfwGetJoystickAxes(0, ctypes.byref(ctypes.c_int(0)))
        print(axes)

if __name__ == "__main__":
    print('Testing...')
    axisTest()
    buttonTest()
    for i in range(GLFW_JOYSTICK_1, GLFW_JOYSTICK_LAST + 1):
        print("Joystick", i, glfw.glfwJoystickPresent(i) == 1)
        try:
            print("\t", repr(glfw.glfwGetJoystickName(i)))
        except:
            pass
    
    from time import sleep
    print("Press a button")
    sleep(1)
    buttonTest(True)
    count = ctypes.c_int(0)
    axes = glfw.glfwGetJoystickAxes(0, ctypes.byref(count))
    print("Here are the states of the " + str(count.value) + " axes:")
    print(axes)
    
    print(str(poll(0)).replace(',', '\n'))
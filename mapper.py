import glob
import json
import time
import math
import sys

import xinput
from xinput import NoControllerError
import robot

class XInputController:
    def __init__(self, name, descriptor):
        self.name = name
        self.descriptor = descriptor
    def mapDescriptor(self, s, root=None, original=None):
        """ s -> XINPUT_GAMEPAD attribute, int for button, else string """
        if root is None:
            return self.mapDescriptor(s.split(" "),
                                      root=self.descriptor['compound'],
                                      original = s)
       
        try:
            n = s.pop(0)
        except IndexError:
            # while searching the compound object, failed to map to full name
            return self.mapToNative(original)

        try:
            if type(root[n]) is dict:
                # there is another layer, continue poking down
                return self.mapDescriptor(s, root=root[n], original=original)
            else:
                # we have reached a name
                return root[n]
        except KeyError:
            # s must be a raw input name or a button
            return self.mapToNative(original)

    def mapToNative(self, n):
        if n in self.descriptor.keys():
            # lets see if it's an axis (which are first-class properties)
            return n
        else:
            # it must be a name of a button
            try:
                return self.descriptor["buttons"].index(n)
            except ValueError:
                raise ValueError("Cannot map \"" + n 
                               + "\" to a controller input")

class Profile:
    def __init__(self, name, profiles, controllerTypes):
        profile = profiles[name]
        self.controller = controllerTypes[profile['controller']]
        if type(self.controller) is not XInputController:
            raise NotImplementedError("Only XInput Controllers are supported")

        self.id = profile['id']
        self.mappings = profile["mappings"]
        
        self.states = {}
        for k, v in self.mappings.items():
            self.states[k] = False
    def poll(self, dt):
        state = xinput.poll(self.id)
        
        for k, v in self.mappings.items():
            # map each mapping description to a computer input
            self.map(dt, state, k, v)
    def map(self, dt, state, mappingInput, mappingOutputDescriptor):
        origin = self.controller.mapDescriptor(mappingInput)
        out = mappingOutputDescriptor
        
        if out['type'] == "state":
            # if the button is pressed and previously was not pressed
            if state['buttons'][origin] and not self.states[mappingInput]:
                # press the key
                self.states[mappingInput] = True
                robot.pressKey(self.parseKeycode(out['target']))
            # if the button is not pressed and previously was pressed
            elif self.states[mappingInput] and not state['buttons'][origin]:
                # release the key
                self.states[mappingInput] = False
                robot.releaseKey(self.parseKeycode(out['target']))
        
        elif out['type'] == "threshold state" and out['threshold'] >= 0:
            # if the state is above the threshold and previously was not
            if self.normalize(state, origin) >= out['threshold'] \
                    and not self.states[mappingInput]:
                # press the key
                self.states[mappingInput] = True
                robot.pressKey(self.parseKeycode(out['target']))
            # if the state is below the threshold and previously was
            elif self.normalize(state, origin) < out['threshold'] \
                    and self.states[mappingInput]:
                # release the key
                self.states[mappingInput] = False
                robot.releaseKey(self.parseKeycode(out['target']))
        elif out['type'] == "threshold state" and out['threshold'] < 0:
            # if the state is above the threshold and previously was not
            if self.normalize(state, origin) <= out['threshold'] \
                    and not self.states[mappingInput]:
                # press the key
                self.states[mappingInput] = True
                robot.pressKey(self.parseKeycode(out['target']))
            # if the state is below the threshold and previously was
            elif self.normalize(state, origin) > out['threshold'] \
                    and self.states[mappingInput]:
                # release the key
                self.states[mappingInput] = False
                robot.releaseKey(self.parseKeycode(out['target']))

        elif out['type'] == "mouse x":
            val = self.normalize(state, origin)
            val = dt * out['speed'] * math.copysign(abs(val)**out['exp'], val)
            robot.translateMouse(val, 0)
        elif out['type'] == "mouse y":
            val = self.normalize(state, origin)
            val = dt * out['speed'] * math.copysign(abs(val)**out['exp'], val)
            robot.translateMouse(0, val)
        
        elif out['type'] == 'click':
            if state['buttons'][origin] and not self.states[mappingInput]:
                # if user is clicking and was not clicking
                self.states[mappingInput] = True
                if (out['target'] == 'left'):
                    robot.mouseButton(robot.MOUSEEVENTF_LEFTDOWN)
                elif (out['target'] == 'middle'):
                    robot.mouseButton(robot.MOUSEEVENTF_MIDDLEDOWN)
                else:
                    robot.mouseButton(robot.MOUSEEVENTF_RIGHTDOWN)
            elif not state['buttons'][origin] and self.states[mappingInput]:
                # if user was clicking but now is not
                self.states[mappingInput] = False
                if (out['target'] == 'left'):
                    robot.mouseButton(robot.MOUSEEVENTF_LEFTUP)
                elif (out['target'] == 'middle'):
                    robot.mouseButton(robot.MOUSEEVENTF_MIDDLEUP)
                else:
                    robot.mouseButton(robot.MOUSEEVENTF_RIGHTUP)
        elif out['type'] == 'threshold click':
            val = self.normalize(state, origin)
            if val >= out['threshold'] and not self.states[mappingInput]:
                # if user is clicking and was not clicking
                self.states[mappingInput] = True
                if (out['target'] == 'left'):
                    robot.mouseButton(robot.MOUSEEVENTF_LEFTDOWN)
                elif (out['target'] == 'middle'):
                    robot.mouseButton(robot.MOUSEEVENTF_MIDDLEDOWN)
                else:
                    robot.mouseButton(robot.MOUSEEVENTF_RIGHTDOWN)
            elif val < out['threshold'] and self.states[mappingInput]:
                # if user was clicking but now is not
                self.states[mappingInput] = False
                if (out['target'] == 'left'):
                    robot.mouseButton(robot.MOUSEEVENTF_LEFTUP)
                elif (out['target'] == 'middle'):
                    robot.mouseButton(robot.MOUSEEVENTF_MIDDLEUP)
                else:
                    robot.mouseButton(robot.MOUSEEVENTF_RIGHTUP)
        
        elif out['type'] == 'scroll y':
            if state['buttons'][origin] and not self.states[mappingInput]:
                self.states[mappingInput] = True
                robot.scrollWheel(out['amount'])
            elif not state['buttons'][origin] and self.states[mappingInput]:
                self.states[mappingInput] = False

    def normalize(self, gamepadState, controllerAxis):
        axis = self.controller.mapDescriptor(controllerAxis)
        info = self.controller.descriptor[axis]
        val = gamepadState[axis]
        
        # TODO: improper, deadzone should be circular, but that would require
        #   getting both the analog inputs which we cant do right now
        dz = info.get('deadzone', 0)
        aMax = info['max']
        aMin = info['min']
        # assume zero centered axis
        if abs(val) > dz:
            if val > 0:
                val -= dz
            else:
                val += dz
            aMax -= dz
            aMin += dz
        else:
            return 0

        val = (val - aMin)/(aMax - aMin)
        # scale the value
        val *= info.get('scale', 1)
        # apply the shift
        val += info.get('shift', 0)
        return val
    def parseKeycode(self, target):
        if target in robot.keys.keys():
            return robot.keys[target]
        
        return robot.getKeyFromAscii(target)

def readControllers():
    with open('./settings/controllers.json', mode='r') as file:
        data = json.load(file)
    
    controllerTypes = {}
    for k, v in data.items():
        controllerTypes[k] = XInputController(k, v)
    
    return controllerTypes
    
def readProfiles():
    # combine all the profiles defined in ./profiles
    files = glob.glob('./profiles/*')
    profiles = {}
    for path in files:        
        with open(path, mode='r') as file:
            data = json.load(file)
        # the new syntax for 3.5 z = {**x, **y}
        # may be too bleeding edge, so just do an old fashion .update
        profiles.update(data)
    
    return profiles

def loop(profile):
    print('Running with 0.01555 delta time.')
    dt = 0.01555
    previous = time.time()
    elapsed = 0
    frames = 0
    all = 0
    try:
        while True:
            current = time.time()
            elapsed += current - previous
            all += current - previous
            previous = current
            
            while elapsed > dt:
                profile.poll(dt)
                elapsed -= dt
                frames += 1
    except KeyboardInterrupt:
        pass

    print('Quitting, did', frames, 'frames in', all,
          'seconds, fps:', frames/all)

if __name__ == "__main__":
    c = readControllers()
    p = readProfiles()
    m = Profile('minecraft', p, c)
    loop(m)
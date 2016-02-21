import glob
import json
import time
import math
import sys
from collections import Iterable

import xinput
from xinput import NoControllerError
import robot

class XInputController:
    def __init__(self, name, descriptor):
        if descriptor['type'] != "xinput":
            raise NotImplementedError("This is not an XInput controller")
        self.name = name
        self.descriptor = descriptor
        self.current = None
        self.previous = None
    def poll(self, id):
        """ Updates the states of the controller """
        # read the state from the computer
        state = xinput.poll(id)
        # update the internal state objects
        if self.previous is None:
            self.previous = state
        else:
            self.previous = self.current
        self.current = state
    def addProfileListeners(self, profile):
        # todo
        for identifier, trigger in profile['mappings'].items():
            # get the triggers assigned to this identifier
            t = self.triggers.setdefault(identifier, [])
            # add the new trigger(s)
            if isinstance(trigger, list):
                # if trigger is a list of triggers
                t.extend(trigger)
            else:
                # trigger must be a single trigger, and should be a dict
                t.append(t)
    def getInput(self, identifier):
        """ identifier -> (type, previous val, current val) """
        type, identifier = self._mapIdentifier(identifier)
        if type == "button":
            return (type, self.previous['buttons'][identifier],
                    self.current['buttons'][identifier])
        elif type == "axis":
            return (type, self.normalize(self.previous, type, identifier),
                    self.normalize(self.current, type, identifier))
        elif type == "vector":
            return (type, self.getVector(self.previous, type, identifier),
                    self.getVector(self.current, type, identifier))
        else:
            raise TypeError("Unkown input type '", type, "'")
    def getVector(self, state, type, identifier):
        if type != "vector":
            raise TypeError("getVector can only retrieve vector inputs, silly")
        
        info = self.descriptor['vector'][identifier]
        # synthesize a dict out of the axes to represent the vector
        # (n.b, vectors can be described in terms of compound identifiers;
        #    we will assume though that they do map to only axes)
        vec = dict((k, self._mapIdentifier(v)) 
                    for k, v in info.items() if k != "normalize")
        # normalize the values, apply axis dead zone if it's specified
        for k, v in vec.items():
            try:
                # v is of form (type, identifier)
                vec[k] = self.normalize(state, *v)
            except TypeError:
                raise TypeError("Vector component can only map to an axis, "
                              + "component " + k + " of " + identifier
                              + " is invalid")
        # apply vector normalization
        self.normalizeVector(vec, identifier)
        return vec
    def normalize(self, state, type, identifier):
        """ Get an axis on the range [0, 1] with regard to its dead zone.
                state should be either self.current or self.previous,
                depending on which value you want to normalize.
        """
        if type != 'axis':
            raise TypeError("Can only normalize axis inputs")

        info = self.descriptor[identifier]
        dz = info.get('deadzone', None)
        raw = state[identifier]
        rMin, rMax = info['min'], info['max']
        if dz is not None:
            raw, rMin, rMax = self.applyRawDeadzone(raw, dz, rMin, rMax)
            if raw == 0:
                return 0
        
        return (raw - rMin)/(rMax - rMin)
    def applyRawDeadzone(self, val, dz, rMin, rMax):
        """ Apply a dead zone to a raw axis value.
                Raw in this context is referring to the value before it is
                mapped to the range [0, 1]; this dead zone is in terms of the raw
                value reported by XInput.
            -> val, new min, new max
        """
        if abs(val) <= dz:
            return 0, rMin, rMax

        # handle the deadzone if the range is [0, m] or [-m, 0]
        if rMin == 0:
            # assume max and val are positive
            return val - dz, 0, rMax - dz
        elif rMax == 0:
            # assume min and val are negative
            return val + dz, rMin + dz, 0
        
        # handle the deadzone if the range spans positive and negative numbers
        # (assume the deadzone is centered)
        return math.copysign(abs(val) - dz, val), rMin + dz, rMax - dz
    def normalizeVector(self, valDict, identifier):
        """ Normalize a vector with regard to its deadzone.
                valDict should be of form, for ex, {x: 0.7, y: 0.6, z: 0.3}
                The axes should already be on the range [0, 1].
                -> None; modifies valDict in place
        """
        info = self.descriptor['vector'][identifier].get('normalize', {})
        magnitude = 0
        dz = info.get('deadzone', 0)
        for k, v in valDict.items():
            # apply the scale and shifts
            v = v * info.get('scale', 1) + info.get('shift', 0)
            # compute the magnitude as we go
            magnitude += v * v
            # assume we are not in the deadzone and calculate the value
            valDict[k] = math.copysign(abs(v) - dz, v)/(1 - dz)
        # if the sqrt(magnitude) is <= dz, replace all values with zero
        if magnitude <= dz * dz:
            for k, v in valDict.items():
                valDict[k] = 0
    def _mapIdentifier(self, identifier):
        """ maps an identifier -> (input type, input name/index) """
        # is identifier a button name?
        try:
            r = self.descriptor['buttons'].index(identifier)
            return ("button", r)
        except ValueError:
            pass
        # is identifier a raw axis name?
        if identifier in self.descriptor.keys():
            return ("axis", identifier)
        # is identifier a vector?
        if identifier in self.descriptor['vector'].keys():
            return ("vector", identifier)
        # is identifier a compound identifier?
        r = self._mapCompoundIdentifier(identifier)
        if r is not None:
            return r
        # identifier appears not to exist
        raise ValueError("Cannot map identifier '", identifier, "' to input.")
    def _mapCompoundIdentifier(self, s, root=None):
        """ -> (input type, input name/index) """
        if root is None:
            return self._mapCompoundIdentifier(s.split(" "),
                                               self.descriptor['compound'])
        nxt = s.pop(0)
        try:
            if type(root[nxt]) is dict:
                # there is another layer, continue poking down
                return self._mapCompoundIdentifier(s, root[nxt])
            else:
                # it must be a string; we have reached an input name
                return self._mapIdentifier(root[nxt])
        except KeyError:
            # doesn't appear to map to anything
            return None

class Profile:
    def __init__(self, name, profiles, controllerTypes):
        profile = profiles[name]
        self.controller = controllerTypes[profile['controller']]

        self.id = profile['id']
        self.mappings = profile["mappings"]
        self.triggers = []
        self.pressed = []
        
        self.validTriggerTypes = ("hold", "press", "release", "repeat", "move")
        self._parseMappings()
    def step(self, dt):
        self.controller.poll(self.id)
        for t in self.triggers:
            getattr(self, 'on' + t['triggerType'].capitalize())(t, dt)
    def onMove(self, trigger, dt):
        if trigger['response'] != 'move mouse':
            raise NotImplementedError('Only move mouse is defined for onMove')
        t, p, c = self.controller.getInput(trigger['triggerSource'])
        if t != 'vector':
            raise TypeError('Only vector types are supported for move mouse')
        info = trigger['info']
        vec = [c[info['x component']], c[info['y component']]]
        vec[0] = math.copysign(abs(vec[0])**info.get('exp', 1), vec[0])
        vec[1] = math.copysign(abs(vec[1])**info.get('exp', 1), vec[1])
        robot.translateMouse(info['x speed'] * dt * vec[0],
                             info['y speed'] * dt * vec[1])
    def onHold(self, trigger, dt):
        t, p, c = self.controller.getInput(trigger['triggerSource'])
        p, c = self._areInputsActive(trigger['info'], t, p, c)
        if not p and c:
            # user just pressed the input
            self.press(trigger['response'], trigger['info'])
        elif p and not c:
            # user just released the input
            self.release(trigger['response'], trigger['info'])
    def onPress(self, trigger, dt):
        t, p, c = self.controller.getInput(trigger['triggerSource'])
        p, c = self._areInputsActive(trigger['info'], t, p, c)
        if not p and c:
            # user just pressed the input
            self.press(trigger['response'], trigger['info'])
            self.release(trigger['response'], trigger['info'])
    def onRelease(self, trigger, dt):
        t, p, c = self.controller.getInput(trigger['triggerSource'])
        p, c = self._areInputsActive(trigger['info'], t, p, c)
        if p and not c:
            # user just released the input
            self.press(trigger['response'], trigger['info'])
            self.release(trigger['response'], trigger['info'])
    def onRepeat(self, trigger, dt):
        raise NotImplementedError("On repeat not yet implemented")
    def press(self, response, info=None):
        self.pressed.append(response)
        if response == "left click":
            robot.mouseButton(robot.MOUSEEVENTF_LEFTDOWN)
        elif response == "right click":
            robot.mouseButton(robot.MOUSEEVENTF_RIGHTDOWN)
        elif response == "middle click":
            robot.mouseButton(robot.MOUSEEVENTF_MIDDLEDOWN)
        elif response == "scroll y":
            robot.scrollWheel(y=info['amount'])
        elif response == "scroll x":
            robot.scrollWheel(x=info['amount'])
        elif response in robot.keys.keys():
            robot.pressKey(robot.keys[response])
        else:
            # assume its a keyboard key
            robot.pressKey(robot.getKeyFromAscii(response))
    def release(self, response, info=None):
        self.pressed.remove(response)
        if response == "left click":
            robot.mouseButton(robot.MOUSEEVENTF_LEFTUP)
        elif response == "right click":
            robot.mouseButton(robot.MOUSEEVENTF_RIGHTUP)
        elif response == "middle click":
            robot.mouseButton(robot.MOUSEEVENTF_MIDDLEUP)
        elif response == "scroll y":
            pass
        elif response == "scroll x":
            pass
        elif response in robot.keys.keys():
            robot.releaseKey(robot.keys[response])
        else:
            # assume its a keyboard key
            robot.releaseKey(robot.getKeyFromAscii(response))
    def _areInputsActive(self, info, t, p, c):
        """ convert axes and vectors into True/False based on thresholds """
        if t == "button":
            return True if p == 1 else False, True if c == 1 else False

        th = info['threshold']
        if t == "axis":
            p = True if p >= th[0] and p <= th[1] else False
            c = True if c >= th[0] and c <= th[1] else False
            return p, c
        if t == "vector":
            vec = p
            p = True if vec[th[0]] >= th[1] and vec[th[0]] <= th[2] else False
            vec = c
            c = True if vec[th[0]] >= th[1] and vec[th[0]] <= th[2] else False
            return p, c
    def _parseMappings(self):
        for inputSrc, triggerDescriptor in self.mappings.items():
            if type(triggerDescriptor) is list:
                for i in triggerDescriptor:
                    res = self._parseMapping(inputSrc, i)
                    self.triggers.append(res)
            else:
                res = self._parseMapping(inputSrc, triggerDescriptor)
                self.triggers.append(res)
    def _parseMapping(self, src, descriptor):
        if type(descriptor) is str:
            action = descriptor
        else:
            try:
                action = descriptor['action']
            except KeyError:
                raise ValueError("Profile mapping '" + src 
                               + "' does not define an action")

        triggerType, response = self._parseAction(action)
        if triggerType not in self.validTriggerTypes:
            raise NotImplementedError("'on" + triggerType
                                    + "' trigger has not been implemented.")
                                    
        # return a single trigger
        return {
            "triggerType": triggerType,
            "response": response,
            "triggerSource": src.strip(),
            "info": descriptor
        }
    def _parseAction(self, action):
        response, triggerType = action.split(" on ")
        return triggerType.strip(), response.strip()

def readControllers():
    with open('./settings/controllers.json', mode='r') as file:
        data = json.load(file)
    
    controllerTypes = {}
    for k, v in data.items():
        if v['type'] != "xinput":
            raise NotImplementedError("Only XInput Controllers are supported.")
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
    dt = 0.014
    print('Running with', dt, 'delta time.')
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
                profile.step(dt)
                elapsed -= dt
                frames += 1
    except KeyboardInterrupt:
        pass
        
    print(profile.pressed)
    print('Quitting, did', frames, 'frames in', all,
          'seconds, fps:', frames/all)

def stick_test(p, c, freq):
    x = c['xbox360']
    import os
    while True:
        x.poll(0)
        print(x.getInput("left stick")[1], 8)
        print(x.getInput("right stick")[1], 8)
        time.sleep(freq)
        os.system('CLS')
    
if __name__ == "__main__":
    c = readControllers()
    p = readProfiles()
    m = Profile('minecraft', p, c)
    loop(m)
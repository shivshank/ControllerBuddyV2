class Responder:
    def __init__(self, trigger):
        # this trigger describes when we need to respond
        self.trigger = trigger
    def respond(self, controller, robot):
        """ This method should be called whenever the input source changes.
            (For simplest implementation, that can be every frame!)
        """
        raise NotImplementedError()
    def booleanize(self):
        """ Convert raw values into True/False.
            If input types are vector/axis, they will be converted based on
            their thresholds as specified by the trigger.
        """
        if inputType == "button":
            return True if p == 1 else False, True if c == 1 else False

        th = self.trigger.info['threshold']
        if inputType == "axis":
            # threshold will be of form [min, max]
            p = True if p >= th[0] and p <= th[1] else False
            c = True if c >= th[0] and c <= th[1] else False
            return p, c
        if inputType == "vector":
            # threshold will be of form [component, min, max]
            comp = th[0]
            vec = p
            p = True if th[1] <= vec[comp] and vec[comp] <= th[2] else False
            vec = c
            c = True if th[1] <= vec[comp] and vec[comp] <= th[2] else False
            return p, c

class OnHold(Responder):
    def __init__(self, trigger):
        super().__init__(trigger)
        # we can guess the state based on the previous and current input value
    def respond(self, controller, mapper):
        p, c = self.booleanize(pinputType, , c)
        if not p and c:
            # user just pressed the input
            self.press(trigger['response'], trigger['info'])
        elif p and not c:
            # user just released the input
            self.release(trigger['response'], trigger['info'])
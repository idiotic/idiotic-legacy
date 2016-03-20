from idiotic.item import _BagOfHolding
from idiotic import timer
import logging
import math

LOG = logging.getLogger("idiotic.declare")

class _ParentProxy:
    def __init__(self, targets):
        self.targets = targets

    def child_changed(self, *args, **kwargs):
        for t in self.targets:
            t.child_changed(*args, **kwargs)

class Condition:
    def __init__(self, parent=None, recalculate_delay=False):
        self.parent = parent
        self.__parents = [parent] if parent else []
        self.__state = None
        self.__set = False
        self.recalculate_delay = recalculate_delay

    @property
    def parent(self):
        return _ParentProxy(self.__parents)

    @parent.setter
    def parent(self, value):
        self.__parents.append(value)

    @property
    def state(self):
        if not self.__set:
            self.recalculate()
            self.__set = True

        return self.__state

    def set_as_parent(self, *children):
        for c in children:
            c.parent = self

    def child_changed(self, child, status):
        self.recalculate()

    def recalculate(self, *_, **__):
        new_state = self.calculate()
        if new_state != self.__state:
            self.__state = new_state

            if self.parent:
                self.parent.child_changed(self, self.state)

            if self.recalculate_delay:
                timer.Timer(self.recalculate_delay, self.recalculate).start()

    def calculate(self):
        return False

    def __and__(self, other):
        return AndCondition(self, other)

    def __or__(self, other):
        return OrCondition(self, other)

    def __neg__(self):
        return NotCondition(self)

    def __invert__(self):
        return NotCondition(self)

    def __xor__(self, other):
        return XorCondition(self, other)

class AndCondition(Condition):
    def __init__(self, *children, **kwargs):
        super().__init__(**kwargs)
        self.children = children
        self.set_as_parent(*children)

    def calculate(self):
        return all((c.state for c in self.children))

class OrCondition(Condition):
    def __init__(self, *children, **kwargs):
        super().__init__(**kwargs)
        self.children = children
        self.set_as_parent(*children)

    def calculate(self):
        return any((c.state for c in self.children))

class XorCondition(Condition):
    def __init__(self, p, q, **kwargs):
        super().__init__(**kwargs)
        self.p = p
        self.q = q
        self.set_as_parent(p, q)

    def calculate(self):
        return self.p.state != self.q.state

class NotCondition(Condition):
    def __init__(self, child, **kwargs):
        super().__init__(**kwargs)
        self.child = child
        self.child.parent = self

    def calculate(self):
        return not self.child.state

class FilterCondition(Condition):
    def __init__(self, target, filt, **kwargs):
        super().__init__(**kwargs)
        self.target = target
        self.filt = filt

    def callback(self):
        self.recalculate()

    def calculate(self):
        return self.filt.check(self.target)

class SceneCondition(Condition):
    def __init__(self, scene, **kwargs):
        super().__init__(**kwargs)

        self.scene = scene
        self.scene.on_enter(self.recalculate)
        self.scene.on_exit(self.recalculate)

    def calculate(self):
        return self.scene.active

class ItemLambdaCondition(Condition):
    def __init__(self, func, *items, **kwargs):
        super().__init__(**kwargs)

        if not items:
            raise ValueError("Must supply one or more items")

        self.func = func
        self.items = items

        for item in self.items:
            item.bind_on_change(self.recalculate)
            item.bind_on_command(self.recalculate)

    def calculate(self):
        return self.func(*self.items)

class StateIsCondition(ItemLambdaCondition):
    def __init__(self, item, state, since=None, **kwargs):
        if since and isinstance(since, int):
            if 'recalculate_delay' not in kwargs:
                # don't override an explicit one
                kwargs['recalculate_delay'] = since

            super().__init__(lambda i: any((h.state == state for h in item.state_history.since(age=since))), item, **kwargs)
        else:
            super().__init__(lambda i: i.state == state, item, **kwargs)

class CommandReceivedCondition(ItemLambdaCondition):
    def __init__(self, item, since, commands=None, **kwargs):
        if commands is None:
            commands = _BagOfHolding()
        else:
            if isinstance(commands, str):
                commands = [commands]
            commands = set(commands)

        if 'recalculate_delay' not in kwargs:
            kwargs['recalculate_delay'] = since

        super().__init__(lambda i: any((h.state in commands for h in item.command_history.since(age=since))), item, **kwargs)

class StateBetweenCondition(ItemLambdaCondition):
    def __init__(self, item, min=-math.inf, max=math.inf, **kwargs):
        super().__init__(lambda i: min < i.state < max, item, **kwargs)

class Action:
    def __init__(self):
        raise NotImplementedError()

class SceneAction(Action):
    def __init__(self, scene, invert=False, do_enter=True, do_exit=True):
        self.scene = scene
        self.invert = invert

        self.do_enter = do_enter
        self.do_exit = do_exit

    def on_state(self, state):
        if state ^ self.invert:
            if self.do_enter:
                self.scene.enter()
        else:
            if self.do_exit:
                self.scene.exit()

class CommandAction(Action):
    def __init__(self, item, yes=None, no=None, both=None, enforce=True):
        self.item = item
        self.yes = yes
        self.no = no
        self.both = both
        self.enforce = enforce

    def on_state(self, state):
        if state and self.yes:
            self.item.command(self.yes)
        elif not state and self.no:
            self.item.command(self.no)

        if self.both:
            self.item.command(self.both)

class StateAction(Action):
    def __init__(self, item, yes=None, no=None, both=None, enforce=False):
        pass

class Rule:
    def __init__(self, condition, both=None, yes=None, no=None):
        self.condition = condition
        self._both = both
        self._yes = yes
        self._no = no

        self.condition.parent = self

    def __call__(self, func):
        """Decorator"""
        self.both(func)

    def both(self, func):
        """Decorator"""
        if not self._both:
            self._both = [func]
        elif callable(self._both) or isinstance(self._both, Action):
            self._both = [self._both, func]
        else:
            self._both.append(func)

    def yes(self, func):
        """Decorator"""
        if not self._yes:
            self._yes = [func]
        elif callable(self._yes) or isinstance(self._yes, Action):
            self._yes = [self._yes, func]
        else:
            self._yes.append(func)

    def no(self, func):
        """Decorator"""
        if not self._no:
            self._no = [func]
        elif callable(self._no) or isinstance(self._no, Action):
            self._no = [self._no, func]
        else:
            self._no.append(func)

    def __dispatch_func(self, funcs, status, include_status):
        if isinstance(funcs, Action):
            funcs.on_state(status)
        elif callable(funcs):
            if include_status:
                funcs(status)
            else:
                funcs()
        else:
            for func in funcs:
                self.__dispatch_func(func, status, include_status)

    def child_changed(self, child, status):
        if self._both:
            self.__dispatch_func(self._both, status, True)

        if status and self._yes:
            self.__dispatch_func(self._yes, status, False)
        elif not status and self._no:
            self.__dispatch_func(self._no, status, False)

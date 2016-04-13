from idiotic.utils import AlwaysInDict, AttrDict
from idiotic import timer
import operator
import asyncio
import logging
import math

LOG = logging.getLogger("idiotic.declare")

class _ParentProxy:
    def __init__(self, targets):
        self.targets = targets

    def child_changed(self, *args, **kwargs):
        for t in self.targets:
            t.child_changed(*args, **kwargs)

def conditify(obj):
    if isinstance(obj, Condition):
        return obj
    return StaticCondition(obj)

class Condition:
    def __init__(self, parent=None, recalculate_delay=False):
        self._parents = [parent] if parent else []
        self.__state = None
        self.__set = False
        self.recalculate_delay = recalculate_delay
        asyncio.get_event_loop().call_soon(self.recalculate)

    @property
    def parent(self):
        return _ParentProxy(self._parents)

    @parent.setter
    def parent(self, value):
        self._parents.append(value)

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
        LOG.debug("{}: Recalculating because child changed to {}".format(self, status))
        self.recalculate()

    def recalculate(self, *_, **__):
        new_state = self.calculate()
        if new_state != self.__state:
            LOG.debug("{}: State changed to {}".format(self, new_state))
            self.__state = new_state

            if self.parent:
                self.parent.child_changed(self, self.state)

            if self.recalculate_delay:
                timer.Timer(self.recalculate_delay, self.recalculate).start()
        else:
            LOG.debug("{}: State stayed the same.".format(self))

    def calculate(self):
        return False

    def __and__(self, other):
        return AndCondition(self, conditify(other))

    def __or__(self, other):
        return OrCondition(self, conditify(other))

    def __neg__(self):
        return NegCondition(self)

    def __invert__(self):
        return NotCondition(self)

    def __xor__(self, other):
        return XorCondition(self, conditify(other))

    def __lt__(self, other):
        return LessCondition(self, conditify(other))

    def __le__(self, other):
        return LessEqualCondition(self, conditify(other))

    def __gt__(self, other):
        return GreaterCondition(self, conditify(other))

    def __ge__(self, other):
        return GreaterEqualCondition(self, conditify(other))

    def __eq__(self, other):
        return EqualCondition(self, conditify(other))

    def __ne__(self, other):
        return NotEqualCondition(self, conditify(other))

    def __add__(self, other):
        return AddCondition(self, conditify(other))

    def __sub__(self, other):
        return SubCondition(self, conditify(other))

    def __mul__(self, other):
        return MulCondition(self, conditify(other))

    def __truediv__(self, other):
        return DivCondition(self, conditify(other))

    def __floordiv__(self, other):
        return FloorDivCondition(self, conditify(other))

    def __mod__(self, other):
        return ModCondition(self, conditify(other))

    def __pow__(self, other):
        return PowCondition(self, conditify(other))

    def __str__(self):
        return "{}".format(type(self))

class StaticCondition(Condition):
    def __init__(self, val, **kwargs):
        super().__init__(**kwargs)

        self.val = val

    def calculate(self):
        return self.val

class OperatorCondition(Condition):
    def __init__(self, oper, *children, **kwargs):
        super().__init__(**kwargs)

        self.oper = oper
        self.children = children

        self.set_as_parent(*self.children)

    def calculate(self):
        return self.oper(*[c.state for c in self.children])

class NegCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.le, *args, **kwargs)

class AddCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.add, *args, **kwargs)

class SubCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.sub, *args, **kwargs)

class MulCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.mul, *args, **kwargs)

class DivCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.truediv, *args, **kwargs)

class FloorDivCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.floordiv, *args, **kwargs)

class ModCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.mod, *args, **kwargs)

class PowCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.pow, *args, **kwargs)

class LessCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.lt, *args, **kwargs)

class LessEqualCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.le, *args, **kwargs)

class GreaterCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.gt, *args, **kwargs)

class GreaterEqualCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.ge, *args, **kwargs)

class EqualCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.eq, *args, **kwargs)

class NotEqualCondition(OperatorCondition):
    def __init__(self, *args, **kwargs):
        super().__init__(operator.ne, *args, **kwargs)

class AndCondition(Condition):
    def __init__(self, *children, **kwargs):
        super().__init__(**kwargs)
        self.children = children
        self.set_as_parent(*children)

    def calculate(self):
        return all((c.state for c in self.children))

    def __str__(self):
        return "(" + " AND ".join((str(c) for c in self.children)) + ")"

class OrCondition(Condition):
    def __init__(self, *children, **kwargs):
        super().__init__(**kwargs)
        self.children = children
        self.set_as_parent(*children)

    def calculate(self):
        return any((c.state for c in self.children))

    def __str__(self):
        return "(" + " OR ".join((str(c) for c in self.children)) + ")"

class XorCondition(Condition):
    def __init__(self, p, q, **kwargs):
        super().__init__(**kwargs)
        self.p = p
        self.q = q
        self.set_as_parent(p, q)

    def calculate(self):
        return self.p.state != self.q.state

    def __str__(self):
        return "{} XOR {}".format(self.p, self.q)

class NotCondition(Condition):
    def __init__(self, child, **kwargs):
        super().__init__(**kwargs)
        self.child = child
        self.child.parent = self

    def calculate(self):
        return not self.child.state

    def __str__(self):
        return "NOT " + str(self.child)

class FilterCondition(Condition):
    def __init__(self, target, filt, **kwargs):
        super().__init__(**kwargs)
        self.target = target
        self.filt = filt

    def callback(self):
        self.recalculate()

    def calculate(self):
        return self.filt.check(self.target)

    def __str__(self):
        return "FilterCondition on {} with filter: {}".format(self.target, self.filt)

class SceneCondition(Condition):
    def __init__(self, scene, **kwargs):
        super().__init__(**kwargs)

        self.scene = scene
        self.scene.on_enter(self.recalculate)
        self.scene.on_exit(self.recalculate)

    def calculate(self):
        return self.scene.active

    def __str__(self):
        return "SceneCondition on {}".format(self.scene)

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

    def __str__(self):
        return "ItemLambdaCondition on {}".format(len(self.items) + " items" if len(self.items) > 1 else self.items[0])

class ChangedSinceCondition(Condition):
    def __init__(self, item, since, **kwargs):
        self.item = item
        self.since = since

        if 'recalculate_delay' not in kwargs:
            kwargs['recalculate_delay'] = since

        super().__init__(lambda i: bool(item.command_history.since(age=since)), item, **kwargs)

    def __str__(self):
        return "StateChangedCondition for {} within {} seconds".format(self.item, self.since)

class StateIsCondition(ItemLambdaCondition):
    def __init__(self, item, state, since=None, **kwargs):
        self.item = item
        self.target = state
        self.since = since
        if since and isinstance(since, int):
            if 'recalculate_delay' not in kwargs:
                # don't override an explicit one
                kwargs['recalculate_delay'] = since

            super().__init__(lambda i: any((h.state == state for h in item.state_history.since(age=since))), item, **kwargs)
        else:
            super().__init__(lambda i: i.state == state, item, **kwargs)

    def __str__(self):
        return "StateIsCondition for {}, state={}".format(self.item, self.target) + ("within {} seconds".format(self.since) if self.since else "")

class CommandReceivedCondition(ItemLambdaCondition):
    def __init__(self, item, since, commands=None, **kwargs):
        if commands is None:
            commands = AlwaysInDict()
        else:
            if isinstance(commands, str):
                commands = [commands]
            commands = set(commands)

        if 'recalculate_delay' not in kwargs:
            kwargs['recalculate_delay'] = since

        self.item = item
        self.since = since
        self.commands = commands

        super().__init__(lambda i: any((h.state in commands for h in item.command_history.since(age=since))), item, **kwargs)

    def __str__(self):
        return "CommandReceivedCondition for {}, commands={}".format(self.item, "any" if self.commands is None else self.commands) + ("within {} seconds".format(self.since) if self.since else "")

class StateBetweenCondition(ItemLambdaCondition):
    def __init__(self, item, min=-2147483648, max=2147483647, **kwargs):
        super().__init__(lambda i: min < i.state < max, item, **kwargs)
        self.item = item
        self.min = min
        self.max = max

    def __str__(self):
        return "StateBetweenCondition {} <= {} <= {}".format(self.min, self.item, self.max)

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
    def __init__(self, item, yes=None, no=None, both=None, enforce=False):
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
    NO_STATE = object()
    def __init__(self, item, yes=NO_STATE, no=NO_STATE, both=NO_STATE, enforce=False):
        self.item = item
        self.yes = yes
        self.no = no
        self.both = both
        self.enforce = enforce

        if self.enforce:
            # TODO find a better way to only cancel events when they
            # try to change the state
            item.bind_on_change(lambda e: e.cancel(), kind="before")
            item.bind_on_command(lambda e: e.cancel(), kind="before")

    def on_state(self, state):
        if state and self.yes != StateAction.NO_STATE:
            self.item.change_state(self.yes)

        if not state and self.no != StateAction.NO_STATE:
            self.item.change_state(self.no)

        if self.both != StateAction.NO_STATE:
            self.item.change_state(self.both)

class Watcher(Condition):
    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.cbs = []
        self.__val = None

    def watch(self, cb):
        self.cbs.append(cb)

    def unwatch(self, cb):
        self.cbs.remove(cb)

    @property
    def val(self):
        return self.__val

    @val.setter
    def val(self, val):
        self.__val = val
        self.recalculate()

    def calculate(self):
        return self.__val

class Watch:
    def __init__(self, *fields):
        self.fields = fields

    def __call__(self, cls):
        for field in self.fields:
            def prop_get(_self):
                return _self.w[field].val

            def prop_set(_self, val):
                _self.w[field].val = val

            setattr(cls, field, property(prop_get, prop_set))

        oldinit = getattr(cls, "__init__")
        def newinit(_self, *args, **kwargs):
            _self.w = AttrDict()
            for f in self.fields:
                _self.w[f] = Watcher(f)
            oldinit(_self, *args, **kwargs)
        setattr(cls, "__init__", newinit)
        return cls

class Rule:
    def __init__(self, condition, both=None, yes=None, no=None):
        self.condition = condition

        if isinstance(both, Condition) or \
           isinstance(yes, Condition) or \
           isinstance(no, Condition):
            raise StateError("Cannot use Condition as an Action! This is probably because of a misplaced comma.")
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
        LOG.debug("Dispatching action to {}".format(funcs))
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
        LOG.debug(str(type(self)) + ": Child changed state")
        if self._both:
            self.__dispatch_func(self._both, status, True)

        if status and self._yes:
            self.__dispatch_func(self._yes, status, False)
        elif not status and self._no:
            self.__dispatch_func(self._no, status, False)

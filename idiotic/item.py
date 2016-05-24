import functools
import datetime
import logging
import idiotic
from collections import defaultdict
from idiotic import event, history, utils
from idiotic.declare import Watch
from typing import Union, get_type_hints

LOG = logging.getLogger("idiotic.item")

def default_command(func):
    setattr(func, "default", True)
    return func

def command(func):
    def command_decorator(self, *args, **kwargs):
        # If we get passed a source (e.g., UI, Rule, Binding), consume
        # it so we don't break our child function
        if "source" in kwargs:
            source = kwargs["source"]
            del kwargs["source"]
        else:
            source = None

        if "command" in kwargs:
            name = kwargs["command"]
        else:
            name = func.__name__

        if name in self.disable_commands:
            LOG.debug("Ignoring disabled command {} on {}".format(name, self))

        LOG.debug("@command({}) on {}".format(name, self))

        if not self.enabled:
            LOG.info("Ignoring command {} on disabled item {}".format(name, self))
            return

        # Create an event and send it
        pre_event = event.CommandEvent(self, name, source, kind="before", args=args, kwargs=kwargs)
        self.idiotic.dispatcher.dispatch_sync(pre_event)

        if not pre_event.canceled:
            func(self, *args, **kwargs)

            self.command_history.record(name)

            if self.idiotic.persist_instance:
                self.idiotic.persist_instance.append_item_history(
                    self, datetime.datetime.now(),
                    name, kind="command",
                    extra={"args": args, "kwargs": kwargs} if args or kwargs else None)

            post_event = event.CommandEvent(self, name, source, kind="after", args=args, kwargs=kwargs)
            self.idiotic.dispatcher.dispatch(post_event)
    command_decorator.command_annotations = get_type_hints(func)
    return command_decorator


def display_formatted(fmtstring):
    def fmt(self):
        return "?" if self.state is None else fmtstring.format(self.state)
    return fmt

def display_unit(unit, precision=2, multiplier=1, type="f", sep=" "):
    def fmt(s):
        return "?" if s.state is None else  "{value:.{precision}{type}}{sep}{unit}".format(value=s.state * multiplier, precision=precision, type=type, unit=unit, sep=sep)
    return fmt

class BaseItem:
    """
.. autoclass:: BaseItem

The base class for an item which implements all the basic
behind-the-scenes functionality and makes no assumptions about the
nature of its state.

    """
    def __init__(self, name, groups=None, friends=None, bindings=None, update=None, tags=None,
                 ignore_redundant=False, aliases=None, id=None, state_translate=lambda s:s,
                 validator=lambda s:s, disable_commands=[], display=lambda s:str(s.state)):
        #: The user-friendly label for the item
        self.name = name
        self._state = None

        if id is None:
            #: The machine-friendly ID for the item. By default, this
            #: is the mangled version of the item's name
            self.id = utils.mangle_name(name)
        else:
            self.id = utils.mangle_name(id)

        #: Whether to generate a state change event when the state is
        #: updated, but has the same value. Defaults to False
        self.ignore_redundant = ignore_redundant

        if tags is None:
            #: A set of tags for this item. Tags qualified with a
            #: module name may have implicit behavior, but otherwise
            #: tags are entirely arbitrary.
            self.tags = set()
        else:
            self.tags = set(tags)

        if groups is None:
            #: A set of groups for this item. The item is also
            #: automatically added to these groups
            self.groups = set()
        else:
            self.groups = set(groups)

        for group in self.groups:
            group.add(self)

        if aliases is None:
            #: A mapping of alias command names to actual command
            #: names. The alias will appear as a normal command for
            #: all intents and purposes
            self.aliases = {}
        else:
            self.aliases = aliases

        #: A list of commands to disable for this item. They will
        #: not appear in the commands list and will be replaced with
        #: a noop
        self.disable_commands = disable_commands

        #: Whether or not this item is disabled. When disabled, it
        #: will ignore all commands and state changes given to it,
        #: until it is enabled again
        self.enabled = True

        self.__command_history = history.History()
        self.__state_history = history.History()

        self.__state_overlay = []

        #: A function that accepts a state and returns a new value to
        #: use for it
        self.state_translate = state_translate

        #: A function that accepts a state and will raise an exception
        #: when it is not valid. When a state is received that causes
        #: an exception, it will be ignored
        self.validator = validator

        self.display = display

        idiotic.instance._register_item(self)

        if bindings:
            for module_name, args in bindings.items():
                LOG.debug("Setting {} bindings on {}".format(module_name, self))
                try:
                    module = self.idiotic.modules[module_name]
                except NameError:
                    LOG.warning("Module '{}' not found -- skipping".format(module_name))
                else:
                    module.bind_item(self, **args)

        if update:
            def wrap_update(item, attr, base_func):
                if attr:
                    setattr(item, attr, base_func(item))
                else:
                    base_func(item)

            if isinstance(update, dict):
                for key, updaters in update.items():
                    for interval, func in updaters:
                        interval.do(wrap_update, self, key, func)
            elif isinstance(update, tuple):
                update[0].do(wrap_update, self, None, update[1])

    def bind_on_command(self, function, **kwargs):
        LOG.debug("Binding on command for {}".format(self))
        self.idiotic.dispatcher.bind(function, utils.Filter(type=event.CommandEvent, item=self, **kwargs))

    def bind_on_change(self, function, **kwargs):
        self.idiotic.dispatcher.bind(function, utils.Filter(type=event.StateChangeEvent, item=self, **kwargs))

    def __str__(self):
        return type(self).__name__ + " '" + self.name + "'"

    def __repr__(self):
        return type(self).__name__ + " '" + self.name + "' on local"

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def has_tag(self, tag):
        return tag and tag.lower() in self.tags

    def add_tag(self, tag):
        self.tags.add(tag)

    def remove_tag(self, tag):
        self.tags.remove(tag)

    def change_state(self, state):
        pass

    def overlay_state(self, state, tag=None, disable=False):
        self.__state_overlay.append({"state": state, "disabled": disable, "tag": tag})
        self.__compute_state_overlay()

    def remove_state_overlay(self, tag=None):
        if tag:
            for i, overlay in enumerate(self.__state_overlay):
                if overlay["tag"] == tag:
                    self.__state_overlay = self.__state_overlay[:i] + self.__state_overlay[i+1:]
                    break
        else:
            self.__state_overlay.pop()
        self.__compute_state_overlay()

    def __compute_state_overlay(self):
        target_state = None
        enabled = None
        for overlay in reversed(self.__state_overlay):
            if "state" in overlay and target_state is None:
                target_state = overlay["state"]

            if "disabled" in overlay and enabled is None:
                enabled = not overlay["disabled"]

        if target_state is not None:
            self.change_state(target_state)
        elif not self.__state_overlay:
            self.change_state(self.state)

        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = True

    @property
    def state(self):
        if self.__state_overlay:
            return self.__state_overlay[-1]["state"]
        return self.state_translate(self._state)

    @state.setter
    def state(self, state):
        self._set_state_from_context(state)

    def command(self, name, *args, **kwargs):
        if name in self.aliases:
            name = self.aliases[name]

        if hasattr(self, name) and callable(getattr(self, name)):
            return getattr(self, name)(*args, **kwargs)
        else:
            raise ValueError("Command {} on item {} does not exist or is not a command".format(name, self))

    def _set_state_from_context(self, val, source="rule"):
        if self.__state_overlay:
            return

        if not self.enabled:
            LOG.info("Ignoring state change on disabled item {}".format(self))
            return

        try:
            val = self.validator(val)
        except:
            LOG.warn("{} not setting state to {} because it did not validate".format(self, val))
            return

        # We don't send an event if there has been literally no change
        if self._state == val and self.ignore_redundant:
            LOG.debug("Ignoring redundant state change for {}".format(self))
            return

        if self._state != val:
            LOG.info("{} changed state from {} -> {}".format(self, self._state, val))

        old = self._state
        pre_event = event.StateChangeEvent(self, old, val, source, kind="before")
        self.idiotic.dispatcher.dispatch(pre_event)
        if not pre_event.canceled:
            self._state = val

            self.__state_history.record(self._state)

            for group in self.groups:
                group._member_state_changed(self, self._state, source)

            post_event = event.StateChangeEvent(self, old, val, source, kind="after")
            self.idiotic.dispatcher.dispatch(post_event)

    @property
    def state_history(self):
        return self.__state_history

    @property
    def command_history(self):
        return self.__command_history

    @property
    def display(self):
        return self._display(self)

    @display.setter
    def display(self, val):
        self._display = val

    def commands(self):
        return { k: {
            "arguments": {
                l: w for l, w in getattr(self, k).command_annotations.items() if l != "return"
            }, "default": getattr(getattr(self, k), "default", False),
        }
                 for k in dir(self)
                 if callable(getattr(self, k, None))
                 and getattr(self, k).__name__ == "command_decorator"
                 and k not in self.disable_commands
        }

    def pack(self):
        res = {
            "__class__": type(self).__name__,
            "__owner__": getattr(self, 'MODULE', 'unknown'),
            "__kind__": "item",
            "__host__": None,
            "__commands__": self.commands(),
            "__attrs__": [k for k in dir(self) if not callable(getattr(self, k, None))
                          and not k.startswith('_')],
            "__methods__": [k for k in dir(self) if callable(getattr(self, k, None))
                            and not k.startswith('_')]
        }

        return res

    def json(self):
        res = {
            "type": type(self).__name__,
            "name": self.name,
            "id": getattr(self, "id", None),
            "tags": list(self.tags),
            "enabled": self.enabled,
            "commands": self.commands(),
            "display": self.display,
            "methods": [k for k in dir(self) if callable(getattr(self, k, None))
                        and not k.startswith('_')],
            "aliases": self.aliases,
        }

        if hasattr(self, "state"):
            res["state"] = self.state

        return res

    def state_translator(self, func):
        self.state_translate = func
        return func


class ItemProxy(BaseItem):
    def __init__(self, idiotic, typename, host, name, commands, attrs, methods,
                 ignore_redundant=False):
        self.typename = typename
        self.host = host
        self.name = name
        self.commands = commands
        self.attrs = attrs
        self.methods = methods
        self._state = None

        self.ignore_redundant = ignore_redundant

        self.idiotic.dispatcher.bind(self.__cache_update, idiotic.utils.Filter(
            item=self.name, type=event.StateChangeEvent))

    def pack(self):
        res = {
            "__class__": self.typename,
            "__host__": self.host,
            "__commands__": self.commands,
            "__attrs__": self.attrs,
            "__methods__": self.methods,
        }

        res.update(self.__dict__)

        return res

    def __cache_update(self, e):
        self._state = e.new

    def _set_state_from_context(self, val, source="rule"):
        if self._state == val and self.ignore_redundant:
            LOG.debug("Ignoring redundant state change for {}".format(self))
            return

        LOG.info("signaling change state on {} from {} -> {}".format(
            self, self._state, val))

        self.idiotic.dispatcher.dispatch(event.SendStateChangeEvent(self.name, val, source))

    def __getattr__(self, attr):
        if attr in self.commands:
            return functools.partial(self.idiotic.dispatcher.dispatch,
                                     event.SendCommandEvent,
                                     source = None)
        elif attr in self.attrs:
            if attr in self._cache:
                return self._cache[attr]
            else:
                raise NotImplementedError("Remote items do not yet support attribute access")

    def __setattr__(self, attr, val):
        if attr in self.attrs:
            self.idiotic.dispatcher.dispatch(event.SendStateChangeEvent(self.name, val, None))
        else:
            raise NameError("Item has no attribute {}".format(attr))

    def __repr__(self):
        return "proxy for " + self.typename + " '" + self.name + "' on " + self.host

    def __eq__(self, other):
        return (isinstance(other, BaseItem) and self.name == other.name) or \
            isinstance(other, str) and other == self.name

    def __req__(self, lhs):
        return self.__eq__(lhs)

class Toggle(BaseItem):
    """An item which has two discrete states between which it may be
    toggled, and which is not affected by repeated identical commands.

    """

    DisplayOnOff = lambda s: "On" if s.state else "Off"
    DisplayOpenClosed = lambda s: "Open" if s.state else "Closed"
    DisplayClosedOpen = lambda s: "Closed" if s.state else "Open"
    DisplayPresentGone = lambda s: "Present" if s.state else "Away"
    DisplayActiveInactive = lambda s: "Active" if s.state else "Inactive"

    def __init__(self, *args, **kwargs):
        if "display" not in kwargs:
            kwargs["display"] = Toggle.DisplayOnOff
        super().__init__(*args, **kwargs)

    def change_state(self, state):
        if state:
            self.on()
        else:
            self.off()
        # otherwise it's already ok

    def _set_state_from_context(self, val, source="rule"):
        if val in ("True", "true", "1", "on"):
            val = True
        elif val in ("False", "false", "0", "off"):
            val = False
        super()._set_state_from_context(bool(val), source)

    @command
    def on(self):
        self.state = True

    @command
    def off(self):
        self.state = False

    @default_command
    @command
    def toggle(self):
        if self.state:
            self.off()
        else:
            self.on()

class Dimmer(Toggle):
    """An item which has an on and off state with a separate value, which
    is applied when the state is on. The value should be between 0 and 1

    """

    DisplayOnOffPercent = lambda s: "On" if s.state == s.max else ("{:.0f}%".format(float(s.state)) if s.state and isinstance(s.state, float) else "Off")

    def __init__(self, *args, min=0, max=1, step=.05, **kwargs):
        self.max = max
        self.min = min
        self.value = self.max
        self.step = step

        if "display" not in kwargs:
            kwargs["display"] = Dimmer.DisplayOnOffPercent
        super().__init__(*args, **kwargs)

    def change_state(self, state):
        self.set(state)

    @command
    def up(self, step: float = None):
        self.set(self.value + (step or self.step))

    @command
    def down(self, step: float = None):
        self.set(self.value - (step or self.step))

    @command
    def full(self):
        self.set(self.max)

    @command
    def set(self, val: float):
        val = max(min(float(val), 1), 0)
        if not val:
            self.off()
        else:
            self.value = val
            self.on()

    @command
    def on(self):
        self.state = self.value

    def json(self):
        res = super().json()
        res.update({
            "value": self.value,
            "max": self.max,
            "min": self.min,
            "step": self.step,
        })
        return res

class SelectorToggle(BaseItem):
    StateOffDisplay = lambda s: str(s.state).title() if s.state else "Off"
    def __init__(self, *args, options=[], **kwargs):
        if "display" not in kwargs:
            kwargs["display"] = lambda s: "Off" if s.state == False else str(s.state).title()
        super().__init__(validator=lambda n: n in self.options, *args, **kwargs)

        self.options = options
        self.last = None

    @command
    def off(self):
        self.last = self.state
        self.state = False

    @command
    def on(self):
        self.state = self.last

    @command
    def select(self, option: str):
        self.state = option

class Trigger(BaseItem):
    """An item with no state, but which may be activated repeatedly,
    triggering a distinct command each time.

    """
    def __init__(self, *args, **kwargs):
        if "display" not in kwargs:
            kwargs["display"] = lambda s: ""
        super().__init__(*args, **kwargs)

    @default_command
    @command
    def trigger(self):
        pass

class Number(BaseItem):
    """An item which represents a numerical quantity of some sort."""

    DisplayPercent = display_unit("%", multiplier=100, sep="")
    DisplayWholePercent = display_unit("%", sep="")

    def __init__(self, *args, kind=float, **kwargs):
        self.kind = kind
        if "display" not in kwargs:
            if kind is float:
                kwargs["display"] = display_formatted("{:.2f}")
            elif kind is int:
                kwargs["display"] = display_formatted("{:d}")
        super().__init__(*args, validator=kind, **kwargs)

    def change_state(self, state):
        self.set(state)

    @default_command
    @command
    def set(self, val: Union[int, float]):
        try:
            self.state = self.kind(val)
        except (ValueError, TypeError):
            LOG.warn("Invalid {} argument to Number.set: {}".format(self.kind.__name__, val))

    @command
    def add(self, val: Union[int, float]):
        try:
            self.state += self.kind(val)
        except (ValueError, TypeError):
            LOG.warn("Invalid {} argument to Number.add: {}".format(self.kind.__name__, val))

    @command
    def sub(self, val: Union[int, float]):
        try:
            self.state -= self.kind(val)
        except (ValueError, TypeError):
            LOG.warn("Invalid {} argument to Number.sub: {}".format(self.kind.__name__, val))

class Text(BaseItem):
    """An item which represents a blob of text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def change_state(self, state):
        self.set(str(state))

    @default_command
    @command
    def set(self, val: str):
        self.state = str(val)

class Motor(BaseItem):
    """An item which can move forward, reverse, and stop."""

    # Options for the current state.
    MOVING_FORWARD = "MOVING_FORWARD"
    MOVING_REVERSE = "MOVING_REVERSE"
    STOPPED = "STOPPED"
    STOPPED_START = "STOPPED_START"
    STOPPED_END = "STOPPED_END"

    STATES = (MOVING_FORWARD,
              MOVING_REVERSE,
              STOPPED)

    STATES_CONSTRAINED = STATES + (STOPPED_START, STOPPED_END)

    _STATES_FB = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Forward", "Moving Back", "Stopped", "Back", "Forward"]))
    DisplayForwardBack = lambda s: Motor._STATES_FB[s]

    _STATES_UD = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Up", "Moving Down", "Stopped", "Down", "Up"]))
    DisplayUpDown = lambda s: Motor._STATES_UD[s]

    _STATES_DU = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Down", "Moving Up", "Stopped", "Up", "Down"]))
    DisplayDownUp = lambda s: Motor._STATES_DU[s]

    _STATES_LR = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Left", "Moving Right", "Stopped", "Right", "Left"]))
    DisplayLeftRight = lambda s: Motor._STATES_LR[s]

    _STATES_RL = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Right", "Moving Left", "Stopped", "Left", "Right"]))
    DisplayRightLeft = lambda s: Motor._STATES_RL[s]

    _STATES_CW = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Clockwise", "Moving Counterclockwise", "Stopped", "Start", "End"]))
    DisplayCW = lambda s: Motor._STATES_CW[s]

    _STATES_CCW = defaultdict(lambda: "?", zip(STATES_CONSTRAINED, [
        "Moving Counterlockwise", "Moving Clockwise", "Stopped", "Start", "End"]))
    DisplayCCW = lambda s: Motor._STATES_CCW[s]

    def __init__(self, *args, constrained=False, timeout=None, **kwargs):
        self.constrained = constrained
        self.timeout = timeout

        if "display" not in kwargs:
            kwargs["display"] = Motor.DisplayForwardBack
        super().__init__(*args, **kwargs)

    def change_state(self, state):
        if state == Motor.MOVING_FORWARD or state == Motor.STOPPED_END:
            self.forward()
        elif state == Motor.MOVING_REVERSE or state == Motor.STOPPED_START:
            self.reverse()
        elif state == Motor.STOPPED:
            self.stop()

    @command
    def forward(self):
        if self.state != Motor.STOPPED_END or not self.constrained:
            self.state = Motor.MOVING_FORWARD
            if self.timeout:
                raise NotImplementedError("timeout is not implemented. probably should do it with asyncio, or implement timers")
        else:
            LOG.debug("Not moving {} forward; already at end stop".format(self))

    @command
    def reverse(self):
        if self.state != Motor.STOPPED_START or not self.constrained:
            self.state = Motor.MOVING_REVERSE
            if self.timeout:
                raise NotImplementedError("timeout is not implemented. probably should do it with asyncio, or implement timers")
        else:
            LOG.debug("Not moving {} reverse; already at start stop".format(self))

    @command
    def stop(self):
        self.state = Motor.STOPPED

class Group(BaseItem):
    """An item which contains other items. It may have custom behavior
    defined to facilitate acting on all its members at once, and to
    summarize its state.

    """
    def __init__(self, *args, state=any, state_set=None, commands=False, command_send=False, members=None, **kwargs):
        """Initialize a Group item, which may or may not handle state updates
        and commands in a custom manner.

        Keyword Arguents:
        state      -- A function which will be used to compute the
                      group's state. It should accept an iterable of
                      BaseItems and return the state. The default is
                      the builtin `any`. If set to `None`, the group
                      will have its own state, indepedent of that
                      of its members.
        state_set  -- A function which will be called when the state
                      of the group is set. It should accept an
                      iterable of BaseItems, and the new state value.
                      This is generally used to set the state of a
                      group's members by changing only the group's
                      state. By default, will do nothing. This
                      argument will be ignored if the 'state'
                      argument is `None`.
        commands   -- How to handle commands sent to the group's
                      members. If `True`, all commands on members of
                      the group will also be sent to the group. If
                      `False`, the group will only receive its own
                      commands. If this argument is an iterable, only
                      commands named by its elements will be passed on
                      to the group, and all others will be ignored.
                      Defaults to `False`.
        command_send -How to handle commands sent to the group itself.
                      If False, commands sent to the group will have
                      no effect. If this is a callable, it will be
                      passed an iterable of BaseItems, the name of the
                      command, and any arguments the command may
                      take. If this is a dictionary, the keys should
                      correspond to command names, while the values
                      are callables for which the commands will be
                      called. The function will be called in the same
                      manner as described previously. Otherwise, this
                      may be set to `True` to automatically call the
                      command on all members of the group.

        """
        super().__init__(*args, **kwargs)

        self.members = members or []

        for item in list(self.members):
            if self not in item.groups:
                item.groups.add(self)

        self._group_state_getter = state
        self._group_state_setter = state_set

        if commands:
            try:
                self.relay_commands = set(commands)
            except TypeError:
                self.relay_commands = utils.AlwaysInDict()
        else:
            self.relay_commands = utils.NeverInDict()

        self.send_commands = {}

        if command_send:
            if command_send is True:
                def dispatch_commands(items, command, *args, **kwargs):
                    for item in items:
                        item.command(command, *args, **kwargs)
                self.send_commands = utils.SingleItemDict(dispatch_commands)
            elif command_send is False:
                self.send_commands = utils.NeverInDict()
            elif callable(command_send):
                self.send_commands = utils.SingleItemDict(command_send)
            elif command_send is not None:
                self.send_commands = dict(command_send)

    def change_state(self, state):
        # TODO add a way to override this
        for item in self.members:
            item.change_state(state)

    def commands(self):
        res = {}

        for item in self.members:
            res.update({k: c for k, c in item.commands().items() if k in self.send_commands})

        return res

    @property
    def state(self):
        if self._group_state_getter:
            return self._group_state_getter(self.members)
        else:
            return super().state

    @state.setter
    def state(self, state):
        if self._group_state_setter:
            self._group_state_setter(self.members, state)
        else:
            # FIXME not sure if this will work
            super().state = state

    def command(self, command=None, *args, **kwargs):
        # Will receive any command by name
        if command and command in self.send_commands:
            self.send_commands[command](self.members, command, *args, **kwargs)

    def flattened(self, include_subgroups=False):
        """Return this group's members and all members of its subgroups, as a
        single list.

        Keyword arguments:
        include_subgroups -- If True, include each subgroup along with its
                             members. Otherwise, subgroups will not be
                             included but their members will be.
        """
        for item in self.members:
            if isinstance(item, Group):
                if include_subgroups:
                    yield item
                yield from item.flattened(include_subgroups)
            else:
                yield item

    def add(self, item):
        if item not in self.members:
            self.members.append(item)

    def _member_state_changed(self, member, state, source):
        if self._group_state_getter:
            post_event = event.StateChangeEvent(self, None, self.state, "group_member," + source, kind="after")
            self.idiotic.dispatcher.dispatch(post_event)

    def json(self):
        res = super().json()

        res.update({"members": [item.name for item in self.members]})
        return res

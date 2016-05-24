from idiotic.utils import Filter
from asyncio import coroutine, iscoroutine, iscoroutinefunction, Queue, QueueFull, get_event_loop
try:
    # timeout is only on 3.5.2+
    from asyncio import timeout
except ImportError:
    # But aiohttp has the same thing already
    from aiohttp import Timeout as timeout
import logging
import functools

LOG = logging.getLogger("idiotic.dispatch")

class Dispatcher:
    def __init__(self):
        self.bindings = []
        self.queue = Queue()

    def bind(self, action, filt=Filter()):
        # The default filter will always return True
        self.bindings.append( (action, filt) )

    def unbind(self, action):
        for action, filt in list(self.bindings):
            self.bindings.remove( (action, filt) )
            return True
        return False

    def dispatch(self, event, time=10):
        for action in (a for a, f in self.bindings if f.check(event)):
            LOG.debug("Dispatching {}".format(str(action)))
            try:
                self.queue.put_nowait((functools.partial(action, event), timeout(time)))
            except QueueFull:
                LOG.error("The unbounded queue is full! Pretty weird, eh?")

    def dispatch_sync(self, event, time=10):
        loop = get_event_loop()

        for target in (a for a, f in self.bindings if f.check(event)):
            LOG.debug("Dispatching {} synchronously".format(str(target)))
            try:
                if iscoroutinefunction(target):
                    # TODO: This doesn't really work how we want...
                    loop.call_soon(target)
                else:
                    target(event)
            except:
                LOG.exception("Error while running {} in synchronous dispatch:".format(target))

    @coroutine
    def run(self):
        while True:
            func, tout = yield from self.queue.get()
            try:
                if not hasattr(func, "__name__"):
                    setattr(func, "__name__", "<unknown>")
                with tout:
                    res = yield from coroutine(func)()

                while iscoroutine(res):
                    with tout:
                        res = yield from res
            except:
                LOG.exception("Error while running {} from dispatch queue:".format(func))

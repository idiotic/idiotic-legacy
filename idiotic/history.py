import collections
import datetime
import bisect

Entry = collections.namedtuple('Entry', ['time', 'state'])

class History:
    def __init__(self, initial=[], maxlen=None, maxage=None):
        self.values = collections.deque(sorted((Entry(*i) for i in initial)), maxlen=maxlen)

        if isinstance(maxage, int):
            self.maxage = datetime.timedelta(seconds=maxage)
        elif isinstance(maxage, datetime.timedelta):
            self.maxage = maxage
        elif maxage is None:
            self.maxage = None
        else:
            raise ValueError("maxage must be int or timedelta")

    def cull(self):
        if self.maxage:
            pos = bisect.bisect_left(list(zip(*self.values))[0], datetime.datetime.now() - self.maxage)
            for _ in range(pos):
                self.values.popleft()

    def record(self, value, time=None):
        if time is None:
            self.values.append(Entry(datetime.datetime.now(), value))
        elif isinstance(time, datetime.datetime):
            if len(self.values) and time < self.values[-1][0]:
                raise NotImplementedError("We can't alter history!... yet....")
            else:
                self.values.append(Entry(time, value))
        else:
            raise ValueError("time must be datetime")

    def closest(self, time=None, age=None):
        if isinstance(time, int):
            time = datetime.datetime.fromtimestamp(seconds=time)

        if age:
            time = datetime.datetime.now() - datetime.timedelta(seconds=age)

        if not self.values:
            return None

        last_after = self.values[-1]
        last_before = None
        for i in reversed(range(len(self.values))):
            if self.values[i].time <= time:
                last_before = self.values[i]
                break
            else:
                last_after = self.values[i]

        if not last_before:
            return last_after

        after_diff = abs(last_after.time - time)
        before_diff = abs(last_before.time - time)
        if after_diff < before_diff:
            return last_after
        else:
            return last_before

    def at(self, time=None, age=None):
        if isinstance(time, int):
            time = datetime.datetime.fromtimestamp(seconds=time)

        if age:
            time = datetime.datetime.now() - datetime.timedelta(seconds=age)

        for i in reversed(range(len(self.values))):
            if self.values[i].time <= time:
                return self.values[i]

        return None

    def since(self, time=None, age=None, include_last=False):
        if isinstance(time, int):
            time = datetime.datetime.fromtimestamp(seconds=time)

        if age:
            time = datetime.datetime.now() - datetime.timedelta(seconds=age)

        for i in reversed(range(len(self.values))):
            if self.values[i].time > time:
                yield self.values[i]
            else:
                if include_last:
                    yield self.values[i]
                raise StopIteration()
        else:
            raise StopIteration()

        return []

    def all(self):
        return list(self.values)

    def last(self, nth=None):
        if nth:
            return list(self.values)[-nth:]
        else:
            if self.values:
                return self.values[-1]
            else:
                return []

    def __len__(self):
        return len(self.values)

    def __getitem__(self, pos):
        return list(self.values)[pos]

    def __str__(self):
        return str(self.values)

from .api import _APIWrapper, join_url, jsonified, single_args
from .etc import mangle_name, IdioticEncoder
import functools
import logging
import imp
import sys
import os

LOG = logging.getLogger("idiotic.utils")

class AttrDict:
    def __init__(self, values={}, throws=NameError):
        self.__values = dict(values)
        self.__throws = throws

    def _set(self, key, value):
        self.__values[mangle_name(key)] = value

    def all(self, filt=None):
        if isinstance(filt, Filter):
            return (v for v in list(self.__values.values()) if filt.check(v))
        elif callable(filt):
            return (v for v in list(self.__values.values()) if filt(v))
        else:
            return self.__values.values()

    def __getattr__(self, key):
        mangled = mangle_name(key)
        if mangled in self.__values:
            return self.__values[mangled]
        else:
            raise self.__throws("Not found: " + key)

    def __getitem__(self, index):
        return getattr(self, index)

    def __setitem__(self, index, val):
        self._set(index, val)

    def __contains__(self, key):
        return key in self.__values

class TaggedDict(AttrDict):
    def with_tags(self, tags):
        ts=set(tags)
        return self.all(filt=lambda i:ts.issubset(i.tags))

class AlwaysInDict:
    def __contains__(self, arg):
        return True

class NeverInDict:
    def __contains__(self, arg):
        return False

class SingleItemDict:
    def __init__(self, item):
        self.item = item

    def __contains__(self, arg):
        return True

    def __getitem__(self, index):
        return self.item

class BaseFilter:
    def __init__(self, *args):
        raise NotImplementedError()

    def __and__(self, other):
        return AndFilter(self, other)

    def __or__(self, other):
        return OrFilter(self, other)

    def __neg__(self):
        return NotFilter(self)

    def __invert__(self):
        return NotFilter(self)

    def __xor__(self, other):
        return XorFilter(self, other)

    def check(self, value):
        return True

class NotFilter(BaseFilter):
    def __init__(self, base):
        if not hasattr(base, "match"):
            raise ValueError("{} has no attribute 'match'".format(base))
        self.__base = base

    def check(self, event):
        return not self.__base.check(event)

    def __str__(self):
        return "NotFilter({})".format(str(self.__base))

    def __repr__(self):
        return "NotFilter({})".format(repr(self.__base))

class AndFilter(BaseFilter):
    def __init__(self, *bases):
        for f in bases:
            if not hasattr(f, "match"):
                raise ValueError("{} has no attribute 'match'".format(f))
        self.__bases = bases

    def match(self, event):
        return all((b.match(event) for b in self.__bases))

    def __str__(self):
        return "AndFilter({})".format(", ".join((str(b) for b in self.__bases)))

    def __repr__(self):
        return "AndFilter({})".format(", ".join((repr(b) for b in self.__bases)))

class OrFilter(BaseFilter):
    def __init__(self, *bases):
        for f in bases:
            if not hasattr(f, "match"):
                raise ValueError("{} has no attribute 'match'".format(f))
        self.__bases = bases

    def match(self, event):
        return any((b.match(event) for b in self.__bases))

    def __str__(self):
        return "OrFilter({})".format(", ".join((str(b) for b in self.__bases)))

    def __repr__(self):
        return "OrFilter({})".format(", ".join((repr(b) for b in self.__bases)))

class XorFilter(BaseFilter):
    def __init__(self, a, b):
        for f in (a, b):
            if not hasattr(f, "match"):
                raise ValueError("{} has no attribute 'match'".format(f))
        self.__a = a
        self.__b = b

    def match(self, event):
        return a.match(event) ^ b.match(event)

    def __str__(self):
        return "XorFilter({}, {})".format(str(a), str(b))

    def __repr__(self):
        return "XorFilter({}, {})".format(repr(a), repr(b))

class Filter(BaseFilter):
    def __init__(self, mode=None, filters=None, **kwargs):
        self.checks = []
        if mode is None:
            self.mode = all
        else:
            self.mode = mode

        if filters:
            # filters is used in case we need to use a reserved word
            # as an argument... though that should probably be avioded
            kwargs.update(filters)

        self.checks_def = kwargs

        for k, v in kwargs.items():
            # I'm very surprised I had to use a closure here. The only
            # other time I had to, I was doing some serious black
            # magic...
            def closure(k,v):
                if "__" in k:
                    key, op = k.rsplit("__", 1)
                else:
                    key, op = "", k
                path = key.split("__")

                if op == "contains":
                    self.checks.append(lambda e:v in self.__resolve_path(e, path))
                elif op == "not_contains":
                    self.checks.append(lambda e:v not in self.__resolve_path(e, path))
                elif op == "in":
                    self.checks.append(lambda e:self.__resolve_path(e, path) in v)
                elif op == "not_in":
                    self.checks.append(lambda e:self.__resolve_path(e, path) not in v)
                elif op == "is":
                    self.checks.append(lambda e:self.__resolve_path(e, path) is v)
                elif op == "is_not":
                    self.checks.append(lambda e:self.__resolve_path(e, path) is not v)
                elif op == "lt":
                    self.checks.append(lambda e:self.__resolve_path(e, path) < v)
                elif op == "gt":
                    self.checks.append(lambda e:self.__resolve_path(e, path) > v)
                elif op == "le":
                    self.checks.append(lambda e:self.__resolve_path(e, path) <= v)
                elif op == "ge":
                    self.checks.append(lambda e:self.__resolve_path(e, path) >= v)
                elif op == "ne":
                    self.checks.append(lambda e:self.__resolve_path(e, path) != v)
                elif op == "match":
                    self.checks.append(lambda e:v(self.__resolve_path(e, path)))
                elif op == "not_match":
                    self.checks.append(lambda e:not v(self.__resolve_path(e, path)))
                elif op == "eq":
                    self.checks.append(lambda e:self.__resolve_path(e, path) == v)
                elif op == "type":
                    self.checks.append(lambda e:type(self.__resolve_path(e, path)) == v)
                elif op == "type_not":
                    self.checks.append(lambda e:type(self.__resolve_path(e, path)) != v)
                elif op == "isinstance":
                    self.checks.append(lambda e:isinstance(self.__resolve_path(e, path), v))
                elif op == "not_isinstance":
                    self.checks.append(lambda e:not isinstance(self.__resolve_path(e, path), v))
                elif op == "hasattr":
                    self.checks.append(lambda e:hasattr(self.__resolve_path(e, path), v))
                elif op == "not_hasattr":
                    self.checks.append(lambda e:not hasattr(self.__resolve_path(e, path), v))
                else:
                    # By default just check for equality
                    path.append(op)
                    self.checks.append(lambda e:self.__resolve_path(e, path) == v)
            closure(k,v)

    def check(self, event):
        res = self.mode(c(event) for c in self.checks)
        return res

    def __resolve_path(self, e, path):
        # TODO make this function
        cur = e
        for key in path:
            if key:
                try:
                    cur = getattr(cur, key)
                except AttributeError:
                    return None
        return cur

    def __str__(self):
        return "Filter({})".format(", ".join(self.checks_def))

    def __repr__(self):
        return "Filter({})".format(", ".join(
            ("{}=<{}>".format(k.replace("__","."),repr(v)) for k,v in self.checks_def.items())))

def load_single(f, include_assets=False):
    LOG.info("Loading file {}...".format(f))
    name = os.path.splitext(f)[0]
    if os.path.isdir(f):
        LOG.info("Attempting to load directory {} as a module...".format(
            os.path.join(f)))

        try:
            mod = imp.load_source(name, os.path.join(f, '__init__.py'))
            assets = None
            if os.path.exists(os.path.join(f, 'assets')) and \
               os.path.isdir(os.path.join(f, 'assets')):
                assets = os.path.abspath(os.path.join(f, 'assets'))

            return (mod, assets)
        except FileNotFoundError:
            LOG.error("Unable to load module {}: {} does not exist".format(
                name, os.path.join(f, '__init__.py')))
    else:
        return (imp.load_source(name, os.path.join(f)), None)


def load_dir(path, include_assets=False, ignore=[]):
    sys.path.insert(1, os.path.abspath("."))
    modules = []
    for f in os.listdir(path):
        try:
            if f.startswith(".") or f.endswith("~") or f.endswith("#") or f.startswith("__") \
               or os.path.splitext(f)[0] in ignore:
                continue

            modules.append(load_single(os.path.join(path, f), include_assets))
        except:
            LOG.exception("Exception encountered while loading {}".format(os.path.join(path, f)))

    return modules

__ALL__ = [AttrDict, TaggedDict, AlwaysInDict, NeverInDict, SingleItemDict, mangle_name, IdioticEncoder, load_dir, _APIWrapper, join_url, jsonified, single_args]

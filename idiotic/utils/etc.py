import json
import typing
import datetime
import collections

def mangle_name(name):
    return ''.join((x for x in name.lower().replace(" ", "_") if x.isalnum() or x=='_')) if name else ""

class TypeAnnotationEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def default(self, obj):
        if type(obj) == typing.AnyMeta:
            return "__Any__"
        elif type(obj) == typing.UnionMeta:
            return {"__Union__": obj.__union_params__}
        elif type(obj) == typing.TupleMeta:
            return {"__Tuple__": obj.__tuple_params__ + (("...",) if obj.__tuple_use_ellipsis else ())}
        elif type(obj) == typing.GenericMeta:
            if obj.__extra__ == collections.abc.MutableMapping:
                return {"__Dict__": obj.__parameters__}
            elif obj.__extra__ == collections.abc.MutableSequence:
                return {"__List__": obj.__parameters__}
            elif obj.__extra__ == collections.abc.MutableSet:
                return {"__Set__": obj.__parameters__}
        elif type(obj) == type:
            return getattr(obj, "__name__")
        else:
            return super().default(obj)

class IdioticEncoder(TypeAnnotationEncoder):
    def __init__(self, *args, depth=-1, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = depth

    def default(self, obj):
        if obj is None:
            return "null"
        elif hasattr(obj, "json"):
            return obj.json()
        elif hasattr(obj, "pack"):
            return obj.pack()
        elif isinstance(obj, datetime.datetime):
            return obj.timestamp()
        else:
            return super().default(obj)

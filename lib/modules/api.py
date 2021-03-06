"""api -- built-in API

"""

import logging
from idiotic.utils import jsonified, single_args
from flask import request
from idiotic import version

MODULE_NAME = "api"

log = logging.getLogger("module.api")

def configure(global_config, config, api, assets):
    api.add_url_rule('/api/version', 'give_version', give_version)
    api.add_url_rule('/api/scene/<name>/command/<command>', 'scene_command', scene_command)
    api.add_url_rule('/api/item/<name>/command/<command>', 'item_command', item_command)
    api.add_url_rule('/api/item/<name>/state', 'item_state', item_state, methods=['GET', 'PUT', 'POST'])
    api.add_url_rule('/api/item/<name>/enable', 'item_enable', item_enable)
    api.add_url_rule('/api/item/<name>/disable', 'item_disable', item_disable)
    api.add_url_rule('/api/item/<name>/history', 'item_history', item_history)
    api.add_url_rule('/api/items', 'list_items', list_items)
    api.add_url_rule('/api/scenes', 'list_scenes', list_scenes)
    api.add_url_rule('/api/item/<name>', 'item_info', item_info)

@jsonified
def give_version():
    return dict(VERSION = version.VERSION,
                LISTED  = version.LISTED,
                SOURCE  = version.SOURCE)

@jsonified
def scene_command(name, command, *_, **__):
    scene = scenes[name]
    if command == "enter":
        scene.enter()
    elif command == "exit":
        scene.exit()
    else:
        raise ValueError("{} has no command {}".format(scene, command))
    return bool(scene)

@jsonified
def item_command(name, command, *_, **kwargs):
    args = single_args(request.args)
    item = items[name]
    item.command(command, **args)
    return dict(item=item)

@jsonified
def item_state(name, *args, **kwargs):
    state = request.data
    item = items[name]
    if state:
        if isinstance(state, bytes):
            state = state.decode('UTF-8')
        item.state = state

    return item.state

@jsonified
def item_enable(name, *args, **kwargs):
    item = items[name]
    item.enable()

@jsonified
def item_disable(name, *args, **kwargs):
    item = items[name]
    item.disable()

@jsonified
def item_history(name, *args, **kwargs):
    args = single_args(request.args)

    item = items[name]
    return item.state_history.all()

@jsonified
def list_items(*_, **__):
    return [i.json() for i in items.all()]

@jsonified
def list_scenes():
    return [s.json() for s in scenes.all()]

@jsonified
def item_info(name=None, source=None):
    if name:
        return items[name].json()

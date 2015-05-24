ALL = "ALL"

class TransportMethod:
    NEIGHBOR_CLASS = None
    MODULE_CLASS = None
    ITEM_CLASS = None

    def __init__(self, config):
        raise NotImplemented("Cannot use abstract transport")

    def send(self, event, targets=ALL):
        """Send an event to all or a subset of this node's neighbors.

        """

    def receive(self):
        """Return a generator that returns incoming events, one-by-one."""

    def connect(self):
        """Connect to the main server, if applicable, and all configured or
discovered neighbors as needed.

        """

    def disconnect(self):
        """Disconnect from the main server, if applicable, and all configured
or discovered neighbors as needed.

        """

    def reconnect(self):
        self.disconnect()
        self.connect()

    def neighbors(self):
        """Return a list of neighbors which are currently connected with this
        node.

        """

class RemoteItem:
    def __init__(self, neighbor, name):
        pass

class RemoteModule:
    def __init__(self, neighbor, name):
        pass

class Neighbor:
    def __init__(self, config):
        pass

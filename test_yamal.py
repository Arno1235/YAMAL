from yamal import Node_Manager, Node
import time, pytest

# TODO test server client functionality

class Publisher(Node):

    def run(self):

        time.sleep(1)

        for _ in range(self.args['number of pings']):
            self.publish('ping', time.time())
            time.sleep(0.1)

            if self._close_event.is_set():
                return

class Subscriber(Node):

    def __init__(self, name, mgr, args):
        super().__init__(name, mgr, args)

    def run(self):
        self.subscribe('ping', self.callback_function)

    def callback_function(self, topic, message):
        ping = time.time() - message
        pytest.timings.append(ping)


def test_publish_subscribe():

    pytest.timings = []

    n_pings = 10

    config = {
        'node1': {
            'class name': 'Publisher',
            'location': 'test_yamal.py',
            'args': {'number of pings': n_pings}
            },
        'node2': {
            'class name': 'Subscriber',
            'location': 'test_yamal.py'
            }
        }

    mgr = Node_Manager()

    mgr._start(config)

    print(max(pytest.timings))

    assert len(pytest.timings) == n_pings
    assert max(pytest.timings) < 0.001
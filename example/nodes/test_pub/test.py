from yamal import Node
import time

class Test_Pub(Node):

    def run(self):

        for _ in range(self.args['number of pings']):
            self.publish('ping', time.time())
            time.sleep(1)

            if self._close_event.is_set():
                return

        self.mgr.close_all_nodes()

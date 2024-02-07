from yamal import Node
import time

class Test_Pub(Node):

    def run(self):

        for _ in range(10):
            self.publish("test", time.time())
            time.sleep(1)

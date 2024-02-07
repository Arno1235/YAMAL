from yamal import Node
import time

class Test_Sub(Node):

    def run(self):

        self.subscribe("test", self.callback_function)
        self.listen()

    def callback_function(self, topic, message):

        print(time.time() - message)
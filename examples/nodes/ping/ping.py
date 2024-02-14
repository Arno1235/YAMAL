from yamal import Node
import time


class Ping_Pub(Node):

    def run(self):

        for _ in range(self.args['number of pings']):
            self.publish('ping', time.time())
            time.sleep(1)

            if self._close_event.is_set():
                return


class Ping_Sub(Node):

    def __init__(self, name, mgr, args):
        super().__init__(name, mgr, args)

        self.pings = []

    def run(self):
        self.subscribe('ping', self.callback_function)

    def callback_function(self, topic, message):
        ping = round((time.time() - message) * 1_000_000)
        print(f'received ping {ping}ns')
        self.pings.append(ping)
    
    def before_close(self):
        print('---')
        print(f'average ping: {round(sum(self.pings) / len(self.pings), 2)}ns')
        print(f'max ping: {round(max(self.pings), 2)}ns')
        print(f'min ping: {round(min(self.pings), 2)}ns')
        print('---')
        
        return super().before_close()

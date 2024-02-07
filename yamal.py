import threading
import argparse
import yaml
import importlib.util
import time

class Communciation_Manager:

    def __init__(self):
        self.lock = threading.Lock()
        self.subscriptions = {}
    
    def publish(self, topic, message):
        with self.lock:
            if topic in self.subscriptions:
                for subscriber, callback_function in self.subscriptions[topic]:
                    callback_function(topic, message)

    def subscribe(self, topic, callback_function, subscriber):
        with self.lock:
            if topic not in self.subscriptions:
                self.subscriptions[topic] = []
            self.subscriptions[topic].append((subscriber, callback_function))

    def unsubscribe(self, topic, subscriber):
        with self.lock:
            if topic in self.subscriptions:
                self.subscriptions[topic] = [x for x in self.subscriptions[topic] if x[0] != subscriber]

class Node:

    def __init__(self, name, comm_mgr):
        self.name = name
        self.comm_mgr = comm_mgr

    def publish(self, topic, message):
        self.comm_mgr.publish(topic, message)
    
    def subscribe(self, topic, callback_function):
        self.comm_mgr.subscribe(topic, callback_function, self)

    def unsubscribe(self, topic):
        self.comm_mgr.unsubscribe(topic, self)
    
    def listen(self):
        while True:
            pass


def load_external_node(node_path, class_name):

    spec = importlib.util.spec_from_file_location("node", node_path)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return getattr(module, class_name)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Run LLaMA in tinygrad', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--cfg', type=str, default=None, help='Path to config yaml file')
    parser.add_argument('--verbose', type=int, default=1, help='Verbose level')

    args = parser.parse_args()

    if args.verbose > 0:
        print(f'starting with verbose level {args.verbose} and config file at {args.cfg}')

    with open(args.cfg, 'r') as f:
        config = yaml.full_load(f)


    comm_mgr = Communciation_Manager()

    threads = []
    for name, properties in config.items():

        node = load_external_node(properties['location'], properties['class name'])

        node = node(name, comm_mgr)

        thread = threading.Thread(target=node.run)
        threads.append((name, thread))

        if args.verbose > 1:
            print(f'{name} loaded')
    
    for name, thread in threads:
        thread.start()
        if args.verbose > 0:
            print(f'{name} started')
    
    for name, thread in threads:
        thread.join()
        if args.verbose > 0:
            print(f'{name} joined')
    
    if args.verbose > 0:
        print('all threads stopped')

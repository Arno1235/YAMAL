import threading, multiprocessing
import argparse, yaml
import importlib.util, builtins, inspect
import curses
import time
import cv2



def str_to_bool(s):
    if s.lower() in ('true', 't', 'yes', 'y', '1'):
        return True
    elif s.lower() in ('false', 'f', 'no', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError("Invalid value for boolean argument: '{}'".format(s))

def verbose_print(*args, **kwargs):

    if 'verbose' in kwargs and verbose < kwargs['verbose']:
        return
    
    original_print(*args)



class Node_Manager:

    def __init__(self):
        self.lock = threading.Lock()
        self.subscriptions = {}
        self.threads = []
    
    def _start(self, config):
        for name, properties in config.items():

            node = self._load_external_node(properties['location'], properties['class name'])

            node = node(name, mgr, properties['args'] if 'args' in properties else None)

            thread = threading.Thread(target=node.run, daemon=True)
            self.threads.append((node, thread))

            print(f'{node.name} loaded', verbose=2)
        
        for node, thread in self.threads:
            thread.start()
            print(f'{node.name} started', verbose=1)
        
        for node, thread in self.threads:
            thread.join()
            print(f'{node.name} joined', verbose=1)
        
        print('all threads stopped', verbose=1)
    
    def _load_external_node(self, node_path, class_name):

        spec = importlib.util.spec_from_file_location("node", node_path)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return getattr(module, class_name)
        
    def close_all_nodes(self):

        with self.lock:
            self.subscriptions = []
        
        for node, thread in self.threads:
            node.close()
            print(f'{node.name} closed', verbose=2)
    
    def publish(self, topic, message):
        with self.lock:
            if topic in self.subscriptions:
                for subscriber, callback_function in self.subscriptions[topic]:
                    print(f'publishing... topic: {topic}, subscriber: {subscriber.name}, message: {str(message)}', verbose=3)
                    callback_function(topic, message)

    def subscribe(self, topic, callback_function, subscriber):
        with self.lock:
            if topic not in self.subscriptions:
                self.subscriptions[topic] = []
            self.subscriptions[topic].append((subscriber, callback_function))
            print(f'subscribed {subscriber.name} to {topic}', verbose=3)

    def unsubscribe(self, topic, subscriber):
        with self.lock:
            if topic in self.subscriptions:
                self.subscriptions[topic] = [x for x in self.subscriptions[topic] if x[0] != subscriber]
            print(f'ussubscribed {subscriber.name} to {topic}', verbose=3)
    
    def get_nodes(self):
        for node, thread in self.threads:
            print(f'{node.name} is {"running" if thread.is_alive() else "closed" if node._close_event.is_set() else "standby"}')
    
    def get_topics(self):
        for topic in self.subscriptions:
            print(f'topic: {topic}')
            for subscriber, callback_function in self.subscriptions[topic]:
                print(f' - {subscriber.name}')


class Node:

    def __init__(self, name, mgr, args=None):
        self._close_event = threading.Event()
        self.name = name
        self.mgr = mgr
        self.args = args

    def publish(self, topic, message):
        self.mgr.publish(topic, message)
    
    def subscribe(self, topic, callback_function):
        self.mgr.subscribe(topic, callback_function, self)

    def unsubscribe(self, topic):
        self.mgr.unsubscribe(topic, self)
    
    def before_close(self):
        pass

    def close(self):
        self.before_close()
        self._close_event.set()


class Cli:

    def __init__(self, mgr, verbose):
        self.lock = threading.Lock()
        self._close_event = threading.Event()
        self.mgr = mgr
        self.verbose = verbose
        

        # Initialize curses
        self.stdscr = curses.initscr()
        self.term_h, self.term_w = self.stdscr.getmaxyx()

        curses.cbreak()  # React to keys instantly without requiring Enter
        self.stdscr.keypad(True)  # Enable special keys (e.g., arrows)

        self.line = 0
        builtins.print = self.custom_print

        self.input_thread = threading.Thread(target=self.get_user_input, daemon=True)
        self.input_thread.start()

        time.sleep(1)
    
    def custom_print(self, *args, **kwargs):

        # TODO: print line longer than terminal width
        # TODO: scroll?

        if 'verbose' in kwargs and self.verbose < kwargs['verbose']:
            return
        
        with self.lock:

            y, x = self.stdscr.getyx()
            self.stdscr.addstr(self.line, 0, " ".join(str(arg) for arg in args))
            self.stdscr.move(y, x)
            self.stdscr.refresh()

        self.line += 1
    
    def get_user_input(self):

        # TODO: add posibility for functions with input parameters
        # TODO: add verbose level change command
        # TODO: catch ctrl+c

        commands = [attr for attr in dir(self.mgr) if callable(getattr(self.mgr, attr)) and attr[0] != '_']

        self.stdscr.addstr(self.term_h - 3, 0, "Commands: " + ", ".join(commands))
        self.stdscr.refresh()

        self.stdscr.move(self.term_h - 2, 0)
        self.stdscr.clrtoeol()


        user_input = ''

        while True:
            char = self.stdscr.getch()

            with self.lock:

                if chr(char) == '\n':
                    break

                if char == curses.KEY_BACKSPACE:
                    user_input = user_input[:-1]
                    self.stdscr.clrtoeol()
                    continue

                if chr(char) == '\t':
                    y, _ = self.stdscr.getyx()
                    self.stdscr.move(y, len(user_input))
                    self.stdscr.clrtoeol()

                    possible_commands = [command for command in commands if command[:len(user_input)] == user_input]

                    if len(possible_commands) == 0:
                        self.stdscr.addstr(self.term_h - 1, 0, f'command {user_input} not recognized')

                    elif len(possible_commands) == 1:
                        self.stdscr.addstr(y, 0, possible_commands[0])
                        user_input = possible_commands[0]

                    elif len(possible_commands) > 1:
                        similar_part = ""
                        for i, c in enumerate(possible_commands[0]):
                            for command in possible_commands:
                                if c != command[i]:
                                    break
                            else:
                                similar_part += c
                                continue
                            break

                        self.stdscr.addstr(y, 0, similar_part)
                        user_input = similar_part
                        self.stdscr.addstr(self.term_h - 1, 0, f'{possible_commands}')

                    self.stdscr.move(y, len(user_input))

                    continue
                
            user_input += chr(char)
        

        self.stdscr.move(self.term_h - 1, 0)
        self.stdscr.clrtoeol()

        for command in commands:
            if user_input == str(command):
                # print(inspect.signature(getattr(self.mgr, command)))

                self.stdscr.addstr(self.term_h - 1, 0, f'executing {command}...')

                print(f'{command}:')
                getattr(self.mgr, command)()

                break
        else:
            self.stdscr.addstr(self.term_h - 1, 0, f'command {user_input} not recognized')
        

        self.stdscr.refresh()

        if not self._close_event.is_set():
            self.get_user_input()
    
    def close(self):

        self._close_event.set()

        print('press button to exit cli...', verbose=0)

        self.input_thread.join()

        # Clean up curses
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()


class Image_Display:

    def __init__(self):
        self.image_queue = multiprocessing.Queue()
        self.queue_size = multiprocessing.Value('i', 0)

        self.process = multiprocessing.Process(target=self._display_process)
        self.process.start()
        
    def display(self, image):

        if self.queue_size.value > 3:
            # Clear queue if it gets too large
            print(f'clearing image queue, queue size of {self.queue_size.value} is too large', verbose=2)
            while not self.image_queue.empty():
                self.image_queue.get()
            self.queue_size.value = 0


        self.image_queue.put(image)
        self.queue_size.value += 1
    
    def close(self):
        self.queue_size.value = -1
        self.process.join()

    def _display_process(self):

        while self.queue_size.value != -1:

            while self.queue_size.value == 0:
                cv2.waitKey(1)
            
            if self.queue_size.value > 0:
                image = self.image_queue.get()
                self.queue_size.value -= 1
                cv2.imshow('image', image)
        
        cv2.destroyAllWindows()



if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Run YAMAL', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--cfg', type=str, default=None, help='Path to config yaml file')
    parser.add_argument('--verbose', type=int, default=1, help='Verbose level')
    parser.add_argument('--cli', type=str_to_bool, default='True', help='Run in CLI mode')

    args = parser.parse_args()


    mgr = Node_Manager()
    
    if args.cli:
        cli = Cli(mgr, args.verbose)
    else:
        verbose = args.verbose
        original_print = print
        builtins.print = verbose_print

    if args.verbose > 0:
        print(f'starting with verbose level {args.verbose}, cli: {args.cli} and config file at {args.cfg}')

    with open(args.cfg, 'r') as f:
        config = yaml.full_load(f)

    mgr._start(config)

    if args.cli:
        cli.close()

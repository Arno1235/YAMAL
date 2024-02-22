import threading, multiprocessing
import argparse, yaml, time, copy
import numpy as np, cv2
import importlib.util, builtins, inspect
import curses
import socket, struct

# TODO logging

START_MARKER = b'$START$'
END_MARKER = b'$END$'
SPLIT_MARKER = b'$SPLIT$'
CLOSE_MARKER = b'$CLOSE$'
SUBSCRIPTION_MARKER = b'$SUB$'



def str_to_bool(s):
    if s.lower() in ('true', 't', 'yes', 'y', '1'):
        return True
    elif s.lower() in ('false', 'f', 'no', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError("Invalid value for boolean argument: '{}'".format(s))


def get_arg(args, key, default=None):
    if args is None: return default
    if key not in args: return default
    if isinstance(args, dict): return args[key]
    return getattr(args, key)


class Node_Manager:

    def __init__(self, args=None):
        self._close_event = threading.Event()
        self.lock = threading.Lock()
        self.subscriptions = {}
        self.threads = []

        self.args = args

        if not get_arg(self.args, 'cli', False):
            self.original_print = print
            builtins.print = self._verbose_print
    
    def _verbose_print(self, *args, **kwargs):
        if 'verbose' in kwargs and get_arg(self.args, 'verbose', 1) < kwargs['verbose']:
            return
        self.original_print(*args)
    
    def _start(self, config):
        for name, properties in config.items():

            node = self._load_external_node(properties['location'], properties['class name'])

            node = node(name, self, properties['args'] if 'args' in properties else None)

            thread = threading.Thread(target=node.run, daemon=True)
            self.threads.append((node, thread))

            print(f'{node.name} loaded', verbose=2)
        
        for node, thread in self.threads:
            thread.start()
            print(f'{node.name} started', verbose=1)

        server_thread = None
        if get_arg(self.args, 'server', False):
            self.server_threads = []
            server_thread = threading.Thread(target=self._server, daemon=True)
            server_thread.start()
        
        for node, thread in self.threads:
            thread.join()
            print(f'{node.name} joined', verbose=1)
        
        self._close_event.set()
        
        if server_thread is not None:
            print('waiting for server thread to close, this can take up to 30s ...', verbose=1)
            server_thread.join()
        
        print('all threads stopped', verbose=1)
    
    def _load_external_node(self, node_path, class_name):

        spec = importlib.util.spec_from_file_location("node", node_path)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return getattr(module, class_name)
    
    def _server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((get_arg(self.args, 'ip'), get_arg(self.args, 'port')))

            s.listen()
            print("server is listening for connections...", verbose=1)
            
            while not self._close_event.is_set():
                try:
                    s.settimeout(10)
                    conn, addr = s.accept()

                    node = Socket_Node(f'socket node {len(self.server_threads)}', self, conn)
                    thread = threading.Thread(target=node.run, daemon=True)
                    thread.start()
                    print(f'{node.name} started', verbose=3)
                    self.server_threads.append((node, thread))

                except socket.timeout:
                    pass
            
            for node, thread in self.server_threads:
                node.close()
                print(f'{node.name} closed', verbose=2)
                thread.join()
                print(f'{node.name} joined', verbose=1)
            
        
    def close_all_nodes(self):

        self._close_event.set()

        with self.lock:
            self.subscriptions = []
        
        for node, thread in self.threads:
            node.close()
            print(f'{node.name} closed', verbose=2)
    
    def publish(self, topic, message):
        execute = []
        with self.lock:
            if topic in self.subscriptions:
                for subscriber, callback_function in self.subscriptions[topic]:
                    execute.append((subscriber, callback_function))
        
        for s, e in execute:
            print(f'publishing... topic: {topic}, subscriber: {s.name}, message: {str(message) if len(str(message)) < 32 else "too long"}', verbose=3)
            e(topic, copy.copy(message))

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
    
    def loop(self, for_loop_count=None, for_loop_in=None, while_loop_condition=None):

        assert int(for_loop_count is None) + int(for_loop_in is None) + int(while_loop_condition is None) >= 2, 'cannot set 2 loop condition simultaneously'

        if for_loop_count is not None:
            for index in range(for_loop_count):
                self.loop_event(index)
                if self._close_event.is_set():
                    return
        
        elif for_loop_in is not None:
            for item in for_loop_in:
                self.loop_event(item)
                if self._close_event.is_set():
                    return
        
        elif while_loop_condition is not None:
            while while_loop_condition and not self._close_event.is_set():
                self.loop_event(None)
                if self._close_event.is_set():
                    return

    def loop_event(self, item):
        pass

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


class Client_Manager:

    def __init__(self, args):
        self._close_event = threading.Event()
        self.args = args
        self.conn = None
    
    def _start(self):

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.connect((get_arg(self.args, 'ip'), get_arg(self.args, 'port')))
            time.sleep(1)
            self.conn = conn
            print('connection established', verbose=1)

            thread_listen = threading.Thread(target=self._listen, daemon=True)
            thread_listen.start()

            thread_listen.join()
        
        self.conn = None

    def _listen(self):

        while not self._close_event.is_set():

            message = b''
            while len(message) == 0 or not message[-len(END_MARKER):] == END_MARKER:

                packet = self.conn.recv(4096)

                if self._close_event.is_set():
                    return
                if not packet or len(packet) == 0:
                    continue

                message += packet
            
            for m in message.split(END_MARKER)[:-1]:
                if len(m) == 0:
                    print('something went wrong, message has a length of 0', verbose=1)
                    continue

                if m[:len(START_MARKER)] != START_MARKER:
                    print(f'wrong start marker, expected {START_MARKER}, but got {m[0]}, from message {m}', verbose=1)
                    continue

                m = m[len(START_MARKER):]

                if m == CLOSE_MARKER:
                    return

                if len(m.split(SPLIT_MARKER)) != 3:
                    print(f'cannot recognize message {m}')
                    continue

                dtype, topic, data = m.split(SPLIT_MARKER)
                dtype = dtype.decode()
                topic = topic.decode()

                if dtype == 'STR':
                    print(f'at {topic}, received string: {data.decode()}', verbose=1)
                
                elif dtype == 'INT':
                    print(f'at {topic}, received int: {struct.unpack('!i', data)[0]}', verbose=1)
                
                elif dtype == 'FLOAT':
                    print(f'at {topic}, received float: {struct.unpack('!d', data)[0]}', verbose=1)
                
                elif dtype == 'IMG':
                    print(f'at {topic}, received image', verbose=1)

                    # TODO
                    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

                else:
                    print(f'message dtype not implemented: {dtype}')

    def get_topics(self):
        # TODO
        pass

    def subscribe(self, topic='ping'):

        if self.conn is None:
            print('no connection established', verbose=1)
            return
        
        self.conn.sendall(SUBSCRIPTION_MARKER + topic.encode() + END_MARKER)

        # TODO confirmation?


class Cli:

    # TODO overwrite assert?

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
        # TODO resizing terminal while using

        if 'verbose' in kwargs and self.verbose < kwargs['verbose']:
            return

        with self.lock:

            y, x = self.stdscr.getyx()

            if self.line >= self.term_h - 4:
                self.line = self.term_h - 5

                for l in range(self.line):
                    self.stdscr.move(l, 0)
                    self.stdscr.clrtoeol()
                    self.stdscr.addstr(l, 0, self.stdscr.instr(l + 1, 0))

            self.stdscr.move(self.line, 0)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(self.line, 0, " ".join(str(arg) for arg in args))
            self.stdscr.move(y, x)
            self.stdscr.refresh()

            self.line += 1
    
    def get_user_input(self):

        # TODO: add verbose level change command
        # TODO: catch ctrl+c

        commands = [attr for attr in dir(self.mgr) if callable(getattr(self.mgr, attr)) and attr[0] != '_']

        # with self.lock:

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
                
                if char == curses.KEY_BACKSPACE or chr(char) == '\b':
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

                user_parameters = []

                parameters = inspect.signature(getattr(self.mgr, command)).parameters
                self.stdscr.addstr(self.term_h - 1, 0, f'{", ".join(parameter for parameter in parameters)} necessary for {command}...')
                for parameter in parameters:

                    self.stdscr.move(self.term_h - 2, 0)
                    self.stdscr.clrtoeol()

                    pre_text = f'{parameter}: '
                    self.stdscr.addstr(self.term_h - 2, 0, pre_text)

                    user_parameter_input = ''

                    while True:
                        char = self.stdscr.getch()

                        with self.lock:

                            if chr(char) == '\n':
                                break

                            if char == curses.KEY_BACKSPACE:
                                user_parameter_input = user_parameter_input[:-1]
                                self.stdscr.clrtoeol()
                                continue
                            
                        user_parameter_input += chr(char)
                    
                    user_parameters.append(user_parameter_input)

                self.stdscr.move(self.term_h - 1, 0)
                self.stdscr.clrtoeol()

                self.stdscr.addstr(self.term_h - 1, 0, f'executing {command}...')
                print(f'executing {command}, with {", ".join([parameter + ' : ' + user_parameter for parameter, user_parameter in zip(parameters, user_parameters)])} ...', verbose=1)

                try:
                    getattr(self.mgr, command)(*user_parameters)
                except TypeError:
                    print('only string parameters are supported at the moment')

                break
        else:
            self.stdscr.addstr(self.term_h - 1, 0, f'command {user_input} not recognized')
        

        self.stdscr.refresh()

        if not self._close_event.is_set():
            self.get_user_input()
    
    def close(self):

        self._close_event.set()

        print('press ENTER to exit cli...', verbose=0)

        self.input_thread.join()

        # Clean up curses
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()


class Image_Display:

    def __init__(self, name):
        self.name = name

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

        t = time.time()

        while self.queue_size.value != -1:

            while self.queue_size.value == 0:
                cv2.waitKey(1)
            
            if self.queue_size.value > 0:
                image = self.image_queue.get()
                self.queue_size.value -= 1
                cv2.imshow(self.name, image)
                cv2.setWindowTitle(self.name, f'{self.name} - display fps: {1/(time.time() - t):.2f}')

                t = time.time()
        
        cv2.destroyAllWindows()


class Socket_Node(Node):
    def __init__(self, name, mgr, conn, args=None):
        super().__init__(name, mgr, args)
        self.conn = conn

    def run(self):
        self.loop(while_loop_condition=True)
        
    def loop_event(self, item):

        try:
            self.conn.settimeout(10)
            packet = self.conn.recv(4096)
            if not packet or len(packet) == 0:
                return

            if packet[:len(SUBSCRIPTION_MARKER)] != SUBSCRIPTION_MARKER or packet[-len(END_MARKER):] != END_MARKER:
                print(f'unrecognized format for connection request: {packet}', verbose=1)
                return

            subscription = packet[len(SUBSCRIPTION_MARKER):-len(END_MARKER)].decode()
            print(f'received new connection request for {subscription}', verbose=1)

            self.subscribe(subscription, self.send_message)

        except socket.timeout:
            pass
        except socket.error as e:
            if e.errno == 9:
                pass

    def send_message(self, topic, message):

        # TODO image

        if isinstance(message, str):
            data = START_MARKER + 'STR'.encode() + SPLIT_MARKER + topic.encode() + SPLIT_MARKER + message.encode() + END_MARKER
        elif isinstance(message, int):
            data = START_MARKER + 'INT'.encode() + SPLIT_MARKER + topic.encode() + SPLIT_MARKER + struct.pack('!i', message) + END_MARKER
        elif isinstance(message, float):
            data = START_MARKER + 'FLOAT'.encode() + SPLIT_MARKER + topic.encode() + SPLIT_MARKER + struct.pack('!d', message) + END_MARKER

        else:
            print('cannot send message over socket, message type unsupported')
            return
        
        self.conn.sendall(data)
    
    def before_close(self):
        self.conn.sendall(START_MARKER + CLOSE_MARKER + END_MARKER)
        time.sleep(1)
        self.conn.close()
        return super().before_close()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='run YAMAL', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--cfg', type=str, default=None, help='path to config yaml file')
    parser.add_argument('--verbose', type=int, default=1, help='verbose level')
    parser.add_argument('--cli', type=str_to_bool, default='True', help='run in CLI mode')
    parser.add_argument('--server', action='store_const', const=True, default=False, help='run server')
    parser.add_argument('--client', action='store_const', const=True, default=False, help='run as client')
    parser.add_argument('--ip', type=str, default='127.0.0.1', help='ip address for the server')
    parser.add_argument('--port', type=int, default=65432, help='port for the server')

    args = parser.parse_args()

    assert not(args.server and args.client), 'cannot run as server and client simultaneously, run as client in a different terminal'


    if args.client:

        client = Client_Manager(args)
    
        if args.cli:
            cli = Cli(client, args.verbose)

        print(f'starting client at {args.ip} : {args.port} with verbose level {args.verbose}, cli: {args.cli}', verbose=1)

        # TODO config file
        client._start()

        if args.cli:
            cli.close()


    else:

        mgr = Node_Manager(args)
    
        if args.cli:
            cli = Cli(mgr, args.verbose)

        if args.server:
            print(f'starting with verbose level {args.verbose}, cli: {args.cli}, server at {args.ip} : {args.port} and config file at {args.cfg}', verbose=1)
        else:
            print(f'starting with verbose level {args.verbose}, cli: {args.cli} and config file at {args.cfg}', verbose=1)

        with open(args.cfg, 'r') as f:
            config = yaml.full_load(f)
        

        mgr._start(config)

        if args.cli:
            cli.close()

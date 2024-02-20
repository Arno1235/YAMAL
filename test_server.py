import socket
import threading
import time
import cv2

HOST = '127.0.0.1'
PORT = 65432

START_MARKER = b'$START$'
END_MARKER = b'$END$'
SPLIT_MARKER = b'$SPLIT$'
CLOSE_MARKER = b'$CLOSE$'


class CustomEvent:
    def __init__(self):
        self.event = threading.Event()
        self.is_closed = False

        self.data = None
    
    def send_string_data(self, string_data):

        self.data = START_MARKER + 'STR'.encode() + SPLIT_MARKER + string_data.encode() + END_MARKER
        self.event.set()
        self.event.clear()
    
    def send_img_data(self, img_data):

        self.data = START_MARKER + 'IMG'.encode() + SPLIT_MARKER + cv2.imencode('.png', img_data)[1].tobytes() + END_MARKER
        self.event.set()
        self.event.clear()
    
    def close(self):
        self.data = START_MARKER + CLOSE_MARKER + END_MARKER
        self.event.set()
        self.event.clear()
        time.sleep(1)
        self.is_closed = True
        self.event.set()


def handle_client(conn, addr, custom_event):
    print(f"Connected by {addr}")

    while True:
        custom_event.event.wait()

        if custom_event.is_closed:
            break
        
        conn.sendall(custom_event.data)

    conn.close()


def ping_thread(custom_event):

    time.sleep(5)

    for i in range(5):

        custom_event.send_string_data(f'Ping {i}')
        time.sleep(0.1)
        custom_event.send_img_data(cv2.imread('image.png'))
        time.sleep(0.1)
        custom_event.data = START_MARKER + 'TEST'.encode() + SPLIT_MARKER + 'string_data'.encode() + END_MARKER
        custom_event.event.set()
        custom_event.event.clear()
        time.sleep(0.1)
    
    custom_event.close()



with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))

    s.listen()
    print("Server is listening for connections...")

    custom_event = CustomEvent()

    threading.Thread(target=ping_thread, args=(custom_event, )).start()
    
    while not custom_event.is_closed:
        try:
            s.settimeout(10)
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr, custom_event)).start()
        except socket.timeout:
            pass
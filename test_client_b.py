import socket, struct
import cv2
import numpy as np


HOST = '127.0.0.1'
PORT = 65432

START_MARKER = b'$START$'
END_MARKER = b'$END$'
SPLIT_MARKER = b'$SPLIT$'
CLOSE_MARKER = b'$CLOSE$'
SUBSCRIPTION_MARKER = b'$SUB$'


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    import time
    time.sleep(1)

    s.sendall(SUBSCRIPTION_MARKER + 'ping b'.encode() + END_MARKER)

    while True:

        message = b''

        while len(message) == 0 or not message[-len(END_MARKER):] == END_MARKER:

            packet = s.recv(4096)
            if not packet or len(packet) == 0:
                continue

            message += packet


        for m in message.split(END_MARKER)[:-1]:
            if len(m) == 0:
                print('Something went wrong')
                continue

            if m[:len(START_MARKER)] != START_MARKER:
                print(f'Wrong start marker, expected {START_MARKER}, but got {m[0]}, from message {m}')
                continue

            m = m[len(START_MARKER):]

            if m == CLOSE_MARKER:
                break

            if len(m.split(SPLIT_MARKER)) != 2:
                print(f'Cannot recognize message {m}')
                continue

            dtype, data = m.split(SPLIT_MARKER)
            dtype = dtype.decode()

            if dtype == 'STR':
                print(data.decode())
            
            elif dtype == 'INT':
                print(struct.unpack('!i', data)[0])
            
            elif dtype == 'FLOAT':
                print(struct.unpack('!d', data)[0])
            
            elif dtype == 'IMG':
                print('image received')
                image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                cv2.imshow('Received Image', image)
                cv2.waitKey(1)

            else:
                print(f'Message dtype not implemented: {dtype}')

        else:
            continue
        break
import socket
import cv2
import numpy as np


HOST = '127.0.0.1'
PORT = 65432


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    while True:

        message = b''

        while not str(message).endswith(";EOM'"):

            packet = s.recv(4096)
            if not packet or packet == b'':
                continue

            message += packet
        
        if str(message).startswith("b'CLOSE;"):
            break

        if str(message).startswith("b'STR;"):
            print(message.decode()[4:-4])
        
        elif str(message).startswith("b'IMG;"):
            image = cv2.imdecode(np.frombuffer(message[4:-4], np.uint8), cv2.IMREAD_COLOR)
            cv2.imshow('Received Image', image)
            cv2.waitKey(1)

        else:
            print(f'Message type not implemented: {str(message).split(";")[0]}')
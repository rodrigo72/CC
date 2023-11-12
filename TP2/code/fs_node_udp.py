# testing things out

import socket
import sys

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Socket initialized")
    s.bind(('', 9090))
    print("Successfull bind. Waiting for data.")
    
except socket.error:
    print("Failed to create socket")
    sys.exit()
    
done = False
while not done:
    try:
        data = s.recvfrom(1)
    except Exception as e:
        print("Error: ", e)
        sys.exit()
    
import socket

# TODO: make as input whether this is local or not
SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5555

from local_settings import *

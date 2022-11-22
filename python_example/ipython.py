import socket
from _thread import *
import pickle
from game import Game
from IPython import embed

ANY = socket.gethostbyname('localhost')
server = "10.11.250.207"
port = 5555

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

embed()
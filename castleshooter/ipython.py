from settings import *
from IPython import embed
from redis_utils import redis, rget, rset, redis_lock, rlisten
from time import sleep

from player import Player

def example_lock_func(key):
    print('waiting for lock...')
    with redis_lock(key, client_id=None):
        print('lock acquired! sleeping...')
        sleep(10)
    print('done!')

embed()
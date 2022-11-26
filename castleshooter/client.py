import game
from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock    
from _thread import start_new_thread
from client_utils import client
from packet import (
    Packet, send_ack, send_without_retry, packet_ack_redis_key, packet_handled_redis_key
)


def _handle_payload_from_server(payload: str) -> None:
    if payload.startswith('client_id|') and client.id is None:
        _, raw_client_id = payload.split('|')
        client.set_id(int(raw_client_id))
    else:
        key, data = payload.split('|')
        rset(key, data, client_id=client.id)


def listen_for_server_updates(socket: Any) -> None:
    while True:
        raw_data = socket.recv(4096).decode()
        for datum in raw_data.split(';'):
            print(f'received: {datum}')
            packet = Packet.from_str(datum)
            packet_id = packet.id
            payload = packet.payload
            if packet.is_ack:
                assert packet_id is not None
                # Record in redis that the message has been acked
                rset(packet_ack_redis_key(packet_id), '1', client_id=client.id)
            elif packet_id is None:
                assert payload is not None
                _handle_payload_from_server(payload)
            else:
                assert payload is not None
                with redis_lock(f'handle_payload_from_server|{packet.id}', client_id=client.id):
                    handled_redis_key = packet_handled_redis_key(packet_id, for_client=None)
                    # Want to make sure not to handle the same packet twice due to a re-send, 
                    # if our ack didn't get through
                    if not rget(handled_redis_key, client_id=client.id):
                        _handle_payload_from_server(payload)
                        send_ack(socket, packet_id)
                        rset(handled_redis_key, '1', client_id=client.id)


def client_main() -> None:

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER, PORT))
    print('connected to server!')

    g = game.Game(500,500, client, s)
    start_new_thread(listen_for_server_updates, (s,))
    g.run()


if __name__ == '__main__':
    client_main()
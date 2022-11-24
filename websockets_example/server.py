#!/usr/bin/env python

import asyncio
from websockets import serve

async def echo(websocket):
    async for message in websocket:
        print(message)
        await websocket.send(message)

async def main():
    async with serve(echo, port=6969):
        await asyncio.Future()  # run forever

asyncio.run(main())
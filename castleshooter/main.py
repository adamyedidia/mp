# This is here because pygbag needs a file called main.py that runs the client

import asyncio

from client import client_main

asyncio.run(client_main())
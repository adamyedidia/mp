This project uses Python 3.9.

Can do `pip install -r requirements.txt`

You also need to get redis:

`brew tap redis-stack/redis-stack`

`brew install --cask redis-stack`

`brew services start redis`

You can check that redis is running properly with:

`redis-cli`

To run the server and client in the `castleshooter/` directory, run `python server.py`, and then run any number of clients by running `python client.py` in other terminals.

You should also make a file called `local_settings.py`:

`vi castleshooter/local_settings.py`

and put the following lines of code into it:

```
import socket

SERVER = socket.gethostbyname('localhost')
```

This will make the server you use when running locally be localhost by default. You can add other things into `local_settings.py` to override their default values in `settings.py` without versioning your changes.
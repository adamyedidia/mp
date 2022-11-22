This project uses Python 3.11.

Can do `pip install -r requirements.txt`

pygame needs to be installed separately, sadly:

`pip install pygame --pre`

You also need to get redis:

`brew tap redis-stack/redis-stack`

`brew install --cask redis-stack`

`brew services start redis`

You can check that redis is running properly with:

`redis-cli`

To run the server and client in the `castleshooter/` directory, run `python server.py`, and then run any number of clients by running `python client.py` in other terminals.
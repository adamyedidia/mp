Can do `pip install -r requirements.txt`

pygame needs to be installed separately, sadly:

`pip install pygame --pre`

You also need to get redis:

`brew tap redis-stack/redis-stack`
`brew install --cask redis-stack`
`brew services start redis`

You can check that redis is running properly with:

`redis-cli`

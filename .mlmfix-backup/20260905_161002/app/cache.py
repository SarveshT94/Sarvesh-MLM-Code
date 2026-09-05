from flask_caching import Cache

# We will use SimpleCache (Server RAM) for the MVP. 
# When you scale to AWS later, we just change this to 'RedisCache'.
cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

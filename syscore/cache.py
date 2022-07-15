"""
I use caching a lot

There is the caching in the base system, but that's special uses decorators etc

Here's a more general one
"""

from syscore.objects import missing_data

class Cache(object):
    def __init__(self, parent_object):
        self._parent = parent_object
        self._store = {}

    def get(self, function_instance, *args, **kwargs):
        function_name = function_instance.__name__
        key = _get_key(function_name, args, kwargs)
        value_from_store = self._get_from_store(key)
        if value_from_store is missing_data:
            value_from_store = self._calculate_and_store(key, function_instance, *args, **kwargs)

        return value_from_store

    def _calculate_and_store(self, key: str, function_instance, *args, **kwargs):
        value = function_instance(*args, **kwargs)
        self._put_in_store(key, value)

        return value

    def _put_in_store(self, key: str, value):
        self.store[key] = value

    def _get_from_store(self, key: str):
        return self.store.get(key, missing_data)

    @property
    def store(self) -> dict:
        return self._store

    @property
    def parent(self):
        return self._parent

def _get_key(function_name, tuple_of_args: tuple, dict_of_kwargs: dict) -> str:
    return "%s/%s/%s" % (str(function_name), str(tuple_of_args), str(dict_of_kwargs))

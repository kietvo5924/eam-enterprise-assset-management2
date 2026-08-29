import threading

_thread_local = threading.local()

def set_current_user_id(user_id):
    _thread_local.user_id = user_id

def get_current_user_id():
    return getattr(_thread_local, 'user_id', None)

def clear_current_user_id():
    if hasattr(_thread_local, 'user_id'):
        del _thread_local.user_id

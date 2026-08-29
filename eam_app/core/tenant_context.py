import threading

_thread_local = threading.local()

def set_current_tenant(tenant_id):
    _thread_local.tenant_id = tenant_id

def get_current_tenant():
    return getattr(_thread_local, 'tenant_id', None)

def clear_current_tenant():
    if hasattr(_thread_local, 'tenant_id'):
        del _thread_local.tenant_id

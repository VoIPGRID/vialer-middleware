from threading import Thread


def threaded(fn):
    """
    Decorator to make a function run in his own thread.
    """
    def wrapper(*args, **kwargs):
        Thread(target=fn, args=args, kwargs=kwargs).start()
    return wrapper

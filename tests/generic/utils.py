import os
from select import select
from multiprocessing.pool import ThreadPool


def fd_has_data(fd, timeout=0):
    readable_fd_list, __, __ = select([fd], [], [], timeout)
    return fd in readable_fd_list


class OsFile:
    def __init__(self, fd, encoding=None):
        self.fd = fd
        self.encoding = encoding

    def read(self, n=None, timeout=None):
        if timeout is not None and not fd_has_data(self.fd, timeout):
            raw = b''
        else:
            raw = os.read(self.fd, n or 10000)

        if self.encoding:
            msg = raw.decode(self.encoding)
        else:
            msg = raw

        return msg

    def write(self, msg):
        if self.encoding:
            msg = msg.encode(self.encoding)
        print('msg', msg)
        return os.write(self.fd, msg)


def nonblocking(f, *args, **kwargs):
    ''' Run function f without blocking, returning an async_result handle

    Caller must call get() on the returned object to get the function return
    value. E.g.
    async_result = nonblocking(myFunction, 1, 2, 3, a='foo', b='bar')
    ...
    # Do other things
    ...
    myFunction_return_value = async_result.get()
    '''
    pool = ThreadPool(processes=1)
    async_result = pool.apply_async(f, args=args, kwds=kwargs)
    return async_result

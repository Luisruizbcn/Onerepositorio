from cpython cimport Py_buffer
from libc.stdint cimport (
    intptr_t,
    uint8_t,
)


cdef class CBuffer:
    cdef intptr_t bufaddr

    def __getbuffer__(self, Py_buffer *buffer, int flags):
        cdef Py_ssize_t itemsize = sizeof(uint8_t)
        cdef Py_ssize_t[1] shape = tuple((self.bufsize // itemsize,))
        cdef Py_ssize_t[1] strides = tuple((itemsize,))
        self.bufaddr = self.ptr
        buffer.buf = <void*>self.bufaddr
        # assumes sizeof(unsigned char) == sizeof(uint8_t)
        # TODO: use C11 static_assert macro in Cython
        buffer.format = "B"
        buffer.itemsize = itemsize
        buffer.len = self.bufsize
        buffer.ndim = 1
        buffer.obj = self
        buffer.readonly = 1
        buffer.shape = shape
        buffer.strides = strides
        buffer.suboffsets = NULL

    def __releasebuffer__(self, Py_buffer *buffer):
        pass

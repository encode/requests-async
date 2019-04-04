import asyncio
import os
import ssl

import requests
import h11


class ConnectionManager:
    def __init__(self):
        self.pools = {}

    async def get_connection(self, url, verify, cert, timeout):
        hostname = url.hostname
        port = url.port
        if port is None:
            port = {"http": 80, "https": 443}[url.scheme]

        if url.scheme == "https":
            ssl = await self.get_ssl_context(verify, cert)
        else:
            ssl = False

        if isinstance(timeout, tuple):
            connect_timeout, read_timeout = timeout
        else:
            connect_timeout = timeout
            read_timeout = timeout

        pool_key = self.get_pool_key(url, verify, cert)
        try:
            pool = self.pools[pool_key]
        except KeyError:
            pool = ConnectionPool(hostname, port, ssl, timeout)
            self.pools[pool_key] = pool

        return await pool.acquire_connection()

    def get_pool_key(self, url, verify, cert):
        if url.scheme == "https":
            return (url.hostname, url.port, verify, cert)
        return (url.hostname, url.port)

    async def get_ssl_context(self, verify, cert):
        """
        Return an SSL context.
        """
        if not verify:
            return self.get_ssl_context_no_verify()

        # Run the SSL loading in a threadpool, since it makes disk accesses.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_ssl_context_verify, cert)

    def get_ssl_context_no_verify(self):
        """
        Return an SSL context for unverified connections.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_COMPRESSION
        context.set_default_verify_paths()
        return context

    def get_ssl_context_verify(self, cert):
        """
        Return an SSL context for verified connections.
        """
        ca_bundle_path = requests.utils.DEFAULT_CA_BUNDLE_PATH

        context = ssl.create_default_context()
        if os.path.isfile(ca_bundle_path):
            context.load_verify_locations(cafile=ca_bundle_path)
        elif os.path.isdir(ca_bundle_path):
            context.load_verify_locations(capath=ca_bundle_path)

        if cert is not None:
            if isinstance(cert, str):
                context.load_cert_chain(certfile=cert)
            else:
                context.load_cert_chain(certfile=cert[0], keyfile=cert[1])

        return context


class ConnectionPool:
    """
    A pool of connections to a single host
    """

    def __init__(self, host, port, ssl, timeout, maxsize=10, block=False):
        self.host = host
        self.port = port
        self.ssl = ssl

        self.maxsize = maxsize
        self.block = block
        self.pool = asyncio.LifoQueue(maxsize=maxsize)

        self.is_closed = False

        if isinstance(timeout, tuple):
            self.connect_timeout, self.read_timeout = timeout
        else:
            self.connect_timeout = timeout
            self.read_timeout = timeout

        for _ in range(maxsize):
            self.pool.put_nowait(None)

    async def acquire_connection(self):
        """
        Obtain a connection from the pool, or open a new connection.
        """
        assert not self.is_closed

        conn = None
        if self.block:
            conn = await self.pool.get()
        else:
            try:
                conn = self.pool.get_nowait()
            except asyncio.QueueEmpty:
                conn = None

        if conn is None:
            conn = await self.open_connection()

        # TODO: Check for dropped connections.

        return conn

    async def open_connection(self):
        """
        Open a new connection.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=self.ssl),
                timeout=self.connect_timeout,
            )
        except asyncio.TimeoutError:
            raise requests.ConnectTimeout()

        return HTTPConnection(reader, writer, timeout=self.read_timeout, pool=self)

    async def release_connection(self, conn):
        """
        Release a connection back to the pool.
        """
        if self.is_closed or self.pool.full():
            await conn.close()
        else:
            self.pool.put_nowait(conn)

    async def close(self):
        """
        Close the connection pool.

        Any pending connections in the pool will be closed, and any active
        connections that are later released will be closed at that point.
        """
        self.is_closed = True

        connections = []
        while not self.pool.empty():
            connections.append(self.pool.get_nowait())

        # TODO: use a non-blocking close on all connections,
        # then wait until all connections are closed.
        for connection in connections:
            await connection.close()


class HTTPConnection:
    def __init__(self, reader, writer, timeout, pool):
        self.reader = reader
        self.writer = writer
        self.timeout = timeout
        self.pool = pool
        self.state = h11.Connection(our_role=h11.CLIENT)

    async def receive_event(self):
        event = self.state.next_event()

        while event is h11.NEED_DATA:
            try:
                data = await asyncio.wait_for(self.reader.read(2048), self.timeout)
            except asyncio.TimeoutError:
                raise requests.ReadTimeout()
            self.state.receive_data(data)
            event = self.state.next_event()

        return event

    async def send_event(self, message):
        data = self.state.send(message)
        self.writer.write(data)

    async def release(self):
        if self.pool is None:
            await self.close()
        else:
            await self.pool.release_connection(self)

    async def close(self):
        self.writer.close()
        if hasattr(self.writer, "wait_closed"):
            await self.writer.wait_closed()

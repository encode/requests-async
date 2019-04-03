import asyncio
import os
import ssl

import requests


class ConnectionPool:
    async def get_connection(self, url, verify, cert, timeout):
        hostname = url.hostname
        port = url.port
        if port is None:
            port = {"http": 80, "https": 443}[url.scheme]

        ssl = await self.get_ssl_context(url, verify, cert)

        try:
            return await asyncio.wait_for(
                asyncio.open_connection(hostname, port, ssl=ssl), timeout
            )
        except asyncio.TimeoutError:
            raise requests.ConnectTimeout()

    async def get_ssl_context(self, url, verify, cert):
        """
        Return an SSL context.
        """
        if url.scheme != "https":
            return False

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

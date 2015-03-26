"""XXX: This exists here only as proof-of concept is not actually used anywhere at the moment.

Provide RPC methods for the cryptoassets helper service.
"""

import logging

from wsgiref.simple_server import make_server

from spyne.application import Application
from spyne.decorator import srpc
from spyne.protocol.json import JsonDocument
from spyne.protocol.http import HttpRpc
from spyne.service import ServiceBase
from spyne.model.complex import Iterable
from spyne.model.primitive import UnsignedInteger
from spyne.model.primitive import String
from spyne.server.wsgi import WsgiApplication


class CryptoassetsRPCService(ServiceBase):

    @srpc(UnsignedInteger, _returns=String)
    def create_address(coin, account):
        '''
        Docstrings for service methods do appear as documentation in the
        interface documents. <b>What fun!</b>

        :param name: The name to say hello to
        :param times: The number of times to say hello

        :returns: An array of 'Hello, <name>' strings, repeated <times> times.
        '''
        for i in range(times):
            yield 'Hello, %s' % name


class RPCServer(threading.Thread):

    def __init__(self, app, ip, port):
        self.app = app
        self.ip = ip
        self.port = port

    def run(self):

        # Instantiate the application by giving it:
        #   * The list of services it should wrap,
        #   * A namespace string.
        #   * An input protocol.
        #   * An output protocol.
        application = Application([CryptoassetsRPCService], 'spyne.examples.hello.http',
              # The input protocol is set as HttpRpc to make our service easy to
              # call. Input validation via the 'soft' engine is enabled. (which is
              # actually the the only validation method for HttpRpc.)
              in_protocol=HttpRpc(validator='soft'),

              # The ignore_wrappers parameter to JsonDocument simplifies the reponse
              # dict by skipping outer response structures that are redundant when
              # the client knows what object to expect.
              out_protocol=JsonDocument(ignore_wrappers=True),
          )

        # Now that we have our application, we must wrap it inside a transport.
        # In this case, we use Spyne's standard Wsgi wrapper. Spyne supports
        # popular Http wrappers like Twisted, Django, Pyramid, etc. as well as
        # a ZeroMQ (REQ/REP) wrapper.
        wsgi_application = WsgiApplication(application)

        # More daemon boilerplate
        self.server = make_server(self.ip, self.port, wsgi_application)

        logging.info("listening to http://127.0.0.1:8000")
        logging.info("wsdl is at: http://localhost:8000/?wsdl")

        self.server.serve_forever()


    def stop(self):
        self.server.shutdown()

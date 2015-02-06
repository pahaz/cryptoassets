"""Configuring cryptoassets.core for your project.

Setup SQLAlchemy, backends, etc. based on individual dictionaries or YAML syntax configuration file.
"""

import io
import inspect
import logging
import logging.config

import yaml

from zope.dottedname.resolve import resolve

from sqlalchemy import engine_from_config

from .coin.defaults import COIN_MODEL_DEFAULTS
from .coin.registry import Coin
from .coin.registry import CoinRegistry

from .backend.base import CoinBackend

from .coin import registry as coin_registry

from .event.registry import EventHandlerRegistry
from .event.base import EventHandler

from .service import status
from .app import Subsystem
from .utils.dictutil import merge_dict


#: XXX: logger cannot be used in this module due to order of logger initialization?
logger = None


class ConfigurationError(Exception):
    """ConfigurationError is thrown when the Configurator thinks somethink cannot make sense with the config data."""


class Configurator:
    """Read configuration data and set up Cryptoassets library.

    Reads Python or YAML format config data and then setss :py:class:`cryptoassets.core.app.CryptoassetsApp` up and running  accordingly.
    """

    def __init__(self, app, service=None):
        """
        :param app: :py:class:`cryptoassets.core.app.CryptoassetsApp` instance

        :param service: :py:class:`cryptoassets.core.service.main.Service` instance (optional)
        """
        self.app = app

        self.service = service

        #: Store full parsed configuration as Python dict for later consumption
        self.config = None

    def setup_engine(self, configuration):
        """Setup database engine.

        See ``sqlalchemy.engine_from_config`` for details.

        TODO: Move engine to its own module?

        :param dict configuration: ``engine`` configuration section
        """

        # Do not enable database
        if not self.app.is_enabled(Subsystem.database):
            return

        transaction_retries = configuration.pop("transaction_retries", 3)
        self.app.transaction_retries = transaction_retries

        echo = configuration.get("echo") in (True, "true")
        engine = engine_from_config(configuration, prefix="", echo=echo, isolation_level="SERIALIZABLE")
        return engine

    def setup_backend(self, coin, data):
        """Setup backends.

        :param data: dictionary of backend configuration entries
        """

        # Do not enable
        if not self.app.is_enabled(Subsystem.backend):
            return

        if not data:
            raise ConfigurationError("backends section missing in config")

        data = data.copy()  # No mutate in place
        klass = data.pop("class")
        data["coin"] = coin
        provider = resolve(klass)

        max_tracked_incoming_confirmations = data.pop("max_tracked_incoming_confirmations", 15)

        # Pass given configuration options to the backend as is
        try:
            instance = provider(**data)
        except TypeError as te:
            # TODO: Here we reflect potential passwords from the configuration file
            # back to the terminal
            # TypeError: __init__() got an unexpected keyword argument 'network'
            raise ConfigurationError("Could not initialize backend {} with options {}".format(klass, data)) from te

        assert isinstance(instance, CoinBackend)

        return instance

    def setup_model(self, module):
        """Setup SQLAlchemy models.

        :param module: Python module defining SQLAlchemy models for a cryptocurrency

        :return: :py:class:`cryptoassets.core.coin.registry.CoinModelDescription` instance
        """
        _engine = None

        result = resolve(module)  # Imports module, making SQLAlchemy aware of it
        if not result:
            raise ConfigurationError("Could not resolve {}".format(module))

        coin_description = getattr(result, "coin_description", None)
        if not coin_description:
            raise ConfigurationError("Module does not export coin_description attribute: {}".format(module))

        return coin_description

    def setup_coins(self, coins):

        coin_registry = CoinRegistry()

        if not coins:
            raise ConfigurationError("No cryptocurrencies given in the config.")

        for name, data in coins.items():
            default_models_module = COIN_MODEL_DEFAULTS.get(name)
            models_module = data.get("models", default_models_module)

            if not models_module:
                raise ConfigurationError("Don't know which SQLAlchemy model to use for coin {}.".format(name))

            coin_description = self.setup_model(models_module)

            backend_config = data.get("backend")
            if not backend_config:
                raise ConfigurationError("No backend config given for {}".format(name))

            max_confirmation_count = int(data.get("max_confirmation_count", 15))

            testnet = data.get("testnet") in ("true", True)

            coin = Coin(coin_description, max_confirmation_count=max_confirmation_count, testnet=testnet)

            backend = self.setup_backend(coin, data.get("backend"))

            coin.backend = backend

            coin_registry.register(name, coin)

        return coin_registry

    def setup_event_handlers(self, event_handler_registry):
        """Read notification settings.

        Example notifier format::

            {
                "shell": {
                    "class": "cryptoassets.core.event_handler_registry.shell.ShellNotifier",
                    "script": "/usr/bin/local/new-payment.sh"
                }
            }

        """

        # Do not enable event_handler_registry
        if not self.app.is_enabled(Subsystem.event_handler_registry):
            return

        notifier_registry = EventHandlerRegistry()

        if not event_handler_registry:
            # event_handler_registry not configured
            return

        for name, data in event_handler_registry.items():
            data = data.copy()  # No mutate in place
            klass = data.pop("class")
            provider = resolve(klass)
            # Pass given configuration options to the backend as is
            try:
                instance = provider(**data)
            except TypeError as te:
                # TODO: Here we reflect potential passwords from the configuration file
                # back to the terminal
                # TypeError: __init__() got an unexpected keyword argument 'network'
                raise ConfigurationError("Could not initialize notifier {} with options {}".format(klass, data)) from te

            assert isinstance(instance, EventHandler)
            notifier_registry.register(name, instance)

        return notifier_registry

    def setup_status_server(self, config):
        """Prepare status server instance for the cryptoassets helper service.
        """
        if not config:
            return

        # Do not enable status server
        if not self.app.is_enabled(Subsystem.status_server):
            return

        ip = config.get("ip", "127.0.0.1")
        port = int(config.get("port", "18881"))

        server = status.StatusHTTPServer(ip, port)
        return server

    def setup_service(self, config):
        """Configure cryptoassets service helper process."""
        assert self.service

        # Nothing given, use defaults
        if not config:
            return

        if "broadcast_period" in config:
            self.service.broadcast_period = int(config["broadcast_period"])

    def load_from_dict(self, config):
        """ Load configuration from Python dictionary.

        Populates ``app`` with instances required to run ``cryptocurrency.core`` framework.
        """

        self.app.engine = self.setup_engine(config.get("database"))
        self.app.coins = self.setup_coins(config.get("coins"))

        # XXX: Backwards compatibility ... drop in some point
        self.app.status_server = self.setup_status_server(config.get("status_server") or  config.get("status-server"))

        self.app.event_handler_registry = self.setup_event_handlers(config.get("events"))

        if self.service:
            self.setup_service(config.get("service"))

        self.config = config

    @classmethod
    def setup_service_logging(cls, config):
        """Setup Python loggers for the helper service process.

        :param config: service -> logging configure section.
        """
        if not config:
            # Go with the stderr
            logging.basicConfig()
        else:
            config["version"] = 1
            logging.config.dictConfig(config)

    @classmethod
    def setup_startup(cls, config):
        """Service helper process specific setup when launched from command line.

        Reads configuration ``service`` section, ATM only interested in ``logging`` subsection.

        This is run before the actual Cryptoassets application initialization. We need logging initialized beforehand so that we can print out nice ``$VERSIONNUMBER is starting`` message.
        """

        service = config.get("service", {})
        logging = service.get("logging", None)
        cls.setup_service_logging(logging)

        return config

    @staticmethod
    def prepare_yaml_file(fname):
        """Extract config dictionary from a YAML file."""
        stream = io.open(fname, "rt")
        config = yaml.safe_load(stream)
        stream.close()

        if not type(config) == dict:
            raise ConfigurationError("YAML configuration file must be mapping like")

        return config

    def load_yaml_file(self, fname, overrides={}):
        """Load config from a YAML file.

        :param fname: Path to the YAML file

        :param overrides: Python nested dicts for specific setting overrides
        """
        config = self.prepare_yaml_file(fname)
        merge_dict(config, overrides)
        self.load_from_dict(config)

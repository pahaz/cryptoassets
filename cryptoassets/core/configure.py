"""Configuring cryptoassets.core for your project.

Setup SQLAlchemy, backends, etc. based on individual dictionaries or YAML syntax configuration file.
"""

import io
import inspect

import yaml

from zope.dottedname.resolve import resolve

from pyramid.path import DottedNameResolver

from sqlalchemy import engine_from_config

from .coin.defaults import COIN_MODEL_DEFAULTS
from .coin.registry import Coin
from .coin.registry import CoinRegistry

from .models import GenericWallet

from .backend.base import CoinBackend

from .coin import registry as coin_registry

from .notify.registry import NotifierRegistry
from .notify.base import Notifier

from .service import status
from .app import Subsystem


class ConfigurationError(Exception):
    pass


class Configurator:

    def __init__(self, app):
        self.app = app

        #: Store full parsed configuration as Python dict for later consumption
        self.config = None

    def setup_engine(self, configuration):
        """Setup database engine.

        See ``sqlalchemy.engine_from_config`` for details.

        :param dict configuration: ``engine`` configuration section
        """

        # Do not enable database
        if not self.app.is_enabled(Subsystem.database):
            return

        echo = configuration.get("echo") in (True, "true")
        return engine_from_config(configuration, prefix="", echo=echo)

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
        transaction_retries = data.pop("transaction_retries", 3)
        data["coin"] = coin
        provider = resolve(klass)
        # Pass given configuration options to the backend as is
        try:
            instance = provider(**data)
        except TypeError as te:
            # TODO: Here we reflect potential passwords from the configuration file
            # back to the terminal
            # TypeError: __init__() got an unexpected keyword argument 'network'
            raise ConfigurationError("Could not initialize backend {} with options {}".format(klass, data)) from te

        self.app.transaction_retries = transaction_retries

        assert isinstance(instance, CoinBackend)
        return instance

    def setup_model(self, module):
        """Setup SQLAlchemy models.

        :param module: Python module defining SQLAlchemy models for a cryptocurrency

        :return: GenericWallet instance
        """
        _engine = None

        resolver = DottedNameResolver()

        result = resolver.resolve(module)  # Imports module, making SQLAlchemy aware of it
        if not result:
            raise ConfigurationError("Could not resolve {}".format(module))

        # TODO: Better method of resolving model mapping of coins
        for obj_name in dir(result):
            if obj_name.startswith("_"):
                continue
            obj = getattr(result, obj_name)
            if inspect.isclass(obj):
                if issubclass(obj, (GenericWallet,)):
                    return obj

    def setup_coins(self, coins):

        coin_registry = CoinRegistry()

        if not coins:
            raise ConfigurationError("No cryptocurrencies given in the config.")

        for name, data in coins.items():
            default_models_module = COIN_MODEL_DEFAULTS.get(name)
            models_module = data.get("models", default_models_module)

            if not models_module:
                raise ConfigurationError("Don't know which SQLAlchemy model to use for coin {}.".format(name))

            wallet_model = self.setup_model(models_module)

            backend_config = data.get("backend")
            if not backend_config:
                raise ConfigurationError("No backend config given for {}".format(name))

            coin = Coin(wallet_model)
            backend = self.setup_backend(coin, data.get("backend"))
            coin.backend = backend

            coin_registry.register(name, coin)

        return coin_registry

    def setup_notify(self, notifiers):
        """Read notification settings.

        Example notifier format:

            {
                "shell": {
                    "class": "cryptoassets.core.notifiers.shell.ShellNotifier",
                    "script": "/usr/bin/local/new-payment.sh"
                }
            }
        """

        # Do not enable notifiers
        if not self.app.is_enabled(Subsystem.notifiers):
            return

        notifier_registry = NotifierRegistry()

        if not notifiers:
            # Notifiers not configured
            return

        for name, data in notifiers.items():
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

            assert isinstance(instance, Notifier)
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

    def load_from_dict(self, config):
        """ Load configuration from Python dictionary.

        Populates ``app`` with instances required to run ``cryptocurrency.core`` framework.
        """

        self.app.engine = self.setup_engine(config.get("database"))
        self.app.coins = self.setup_coins(config.get("coins"))
        self.app.status_server = self.setup_status_server(config.get("status-server"))
        self.app.notifiers = self.setup_notify(config.get("notify"))

        self.config = config

    @staticmethod
    def setup_logging(self, config):
        """Setup Python loggers.

        Note: This is not called by default, as your parent application might want to do its own Python logging setup.
        """
        if not config:
            logging.basicConfig()

    @staticmethod
    def load_standalone_from_dict(config):
        setup_logging(config.get("logging"))

    @staticmethod
    def prepare_yaml_file(fname):
        """Extract config dictionary from a YAML file."""
        stream = io.open(fname, "rt")
        config = yaml.safe_load(stream)
        stream.close()

        if not type(config) == dict:
            raise ConfigurationError("YAML configuration file must be mapping like")

        return config

    def load_yaml_file(self, fname):
        """Load config from a YAML file."""
        config = self.prepare_yaml_file(fname)
        self.load_from_dict(config)

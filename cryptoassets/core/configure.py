"""Configuring cryptoassets.core for your project.

Setup SQLAlchemy, backends, etc. based on individual dictionaries or YAML syntax configuration file.
"""

import io

import yaml

from zope.dottedname.resolve import resolve

from pyramid.path import DottedNameResolver

from sqlalchemy import engine_from_config

from .models import DBSession
from .models import Base

from .backend.base import CoinBackend
from .backend import registry

from .notify import registry as notifier_registry
from .notify.base import Notifier


_engine = None
_backends = {}
_models = {}


class ConfigurationError(Exception):
    pass


def setup_engine(configuration):
    """Setup database engine.

    See ``sqlalchemy.engine_from_config`` for details.

    :param dict configuration: Parsed INI-like configuration
    """
    global _engine
    _engine = engine_from_config(configuration, prefix="")


def setup_backends(backends):
    """Setup backends.

    :param backends: dictionary of coin name -> backend data
    """

    if not backends:
        raise ConfigurationError("backends section missing in config")

    for name, data in backends.items():
        data = data.copy()  # No mutate in place
        klass = data.pop("class")
        data["coin"] = name
        provider = resolve(klass)
        # Pass given configuration options to the backend as is
        try:
            instance = provider(**data)
        except TypeError as te:
            # TODO: Here we reflect potential passwords from the configuration file
            # back to the terminal
            # TypeError: __init__() got an unexpected keyword argument 'network'
            raise ConfigurationError("Could not initialize backend {} with options {}".format(klass, data)) from te

        assert isinstance(instance, CoinBackend)
        registry.register(name, instance)


def setup_models(modules):
    """Setup SQLAlchemy models.

    :param modules: List of Python modules defining cryptocurrency models.
    """
    assert _engine

    if not modules:
        raise ConfigurationError("modules section missing in config")

    resolver = DottedNameResolver()

    for name, module in modules.items():
        result = resolver.resolve(module)  # Imports module, making SQLAlchemy aware of it
        if not result:
            raise ConfigurationError("Could not resolve {}".format(module))

    DBSession.configure(bind=_engine)
    Base.metadata.create_all(_engine)


def setup_notify(notifiers):
    """Setup SQLAlchemy models.

    Example notifier format:

        {
            "shell": {
                "class": "cryptoassets.core.notifiers.shell.ShellNotifier",
                "script": "/usr/bin/local/new-payment.sh"
            }
        }
    """
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


def load_from_dict(config):
    """ Load configuration from Python dictionary. """

    setup_engine(config.get("database"))
    setup_backends(config.get("backends"))
    setup_models(config.get("models"))


def load_yaml_file(fname):
    """Load config from a YAML file."""
    stream = io.open(fname, "rt")
    config = yaml.safe_load(stream)

    if not type(config) == dict:
        raise ConfigurationError("YAML configuration file must be mapping like")

    load_from_dict(config)


def check():
    """Check if we are all good to go."""
    if len(registry._backends) == 0:
        raise ConfigurationError("No backends given")

    if len(Base.metadata.tables.keys()) == 0:
        raise ConfigurationError("No models given")

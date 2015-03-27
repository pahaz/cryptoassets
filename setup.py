import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.rst')) as f:
    CHANGES = f.read()

requires = [
    'SQLAlchemy',
    'python-slugify',
    'block-io',
    'rainbow_logging_handler',
    'apscheduler',
    'PyYAML',
    'requests',
    'python-bitcoinrpc'
    ]

setup(name='cryptoassets.core',
      version='0.2',
      description='A Python framework for building Bitcoin, other cryptocurrency (altcoin) and cryptoassets services',
      long_description=README + '\n\n' + CHANGES,
      # https://packaging.python.org/en/latest/distributing.html#classifiers
      classifiers=[
        'Development Status :: 4 - Beta',
        "Programming Language :: Python",
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Topic :: Security :: Cryptography',
        'Intended Audience :: Financial and Insurance Industry'
        ],
      author='Mikko Ohtamaa',
      author_email='mikko@opensourcehacker.com',
      url='https://bitbucket.org/miohtama/cryptoassets',
      keywords='bitcoin litecoin dogecoin sqlalchemy',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='cryptoassets.core',
      install_requires=requires,
      entry_points="""\
      [console_scripts]
      cryptoassets-initialize-database = cryptoassets.core.service.main:initializedb
      cryptoassets-helper-service = cryptoassets.core.service.main:helper
      cryptoassets-scan-received = cryptoassets.core.service.main:scan_received
      """,
      )

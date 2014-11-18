import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'pyramid',
    'pyramid_chameleon',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'SQLAlchemy',
    'transaction',
    'zope.sqlalchemy',
    'waitress',
    'python-slugify',
    'block-io',
    'rainbow_logging_handler',
    'mock'
    ]

setup(name='cryptoassets.core',
      version='0.0',
      description='Bitcoin, cryptocurrency and cryptoassets API, database models and accounting library',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Cryptoassets library authors',
      author_email='mikko@opensourcehacker.com',
      url='https://bitbucket.org/miohtama/cryptoassets',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='cryptoassets.core',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = cryptoassets:main
      [console_scripts]
      initialize_cryptoassets_db = cryptoassets.core.scripts.initializedb:main
      """,
      )

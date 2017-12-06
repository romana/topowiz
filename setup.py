from os import path

from setuptools import setup, find_packages
from codecs import open

import topowiz


here = path.abspath(path.dirname(__file__))


try:
    with open(path.join(here, 'README'), encoding='utf-8') as f:
        long_description = f.read()
except (IOError):
    long_description = "(not available)"


setup(
    name                 = 'topowiz',
    version              = topowiz.__version__,
    url                  = "https://github.com/romana/topowiz",
    license              = "Apache Software License",
    author               = "Juergen Brendel",
    author_email         = "jbrendel@romana.io",
    description          = "Wizard for creation of Romana topology files",
    long_description     = long_description,
    packages             = find_packages(),
    include_package_data = True,
    install_requires     = [
        'argparse>=1.2.1',
        'ipaddr>=2.2.0',
        'Flask>=0.12.2',
        'WTForms>=2.1',
        'Flask-WTF>=0.14.2',
    ],
    classifiers          = [
        'Programming Language :: Python',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Networking'
    ]
)

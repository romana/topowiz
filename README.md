# Romana TopoWiz: The topology wizard

## Installation

TopoWiz was developed on a Ubuntu 14.04 system. It should work on later
versions of Ubuntu as well. Developed with Python 3.4.3 and boto3.

Here are the steps to create a working environment locally:

1. Install some system-wide dependencies:

    $ sudo apt-get install python3-dev

2. Create a virtualenv for the project and change into it:

    $ virtualenv -p python3 topowiz
    $ cd topowiz
    $ source bin/activate
    $ pip3 install --upgrade setuptools
    $ pip3 install --upgrade pip

3. Clone/download the repository and step into the directory:

    $ git clone git@github.com:romana/topowiz.git
    $ cd topowiz

4a. For local development:

    $ pip3 install -r requirements/develop.txt

    Then to run the program (without having to install it):

    $ ./topowiz-runner.py  ....

4b. For deployment:

    $ python setup.py install

    Then to run the program:

    $ topowiz  ....


Developing
----------
To run all unit tests:

    $ ./run_tests.sh

An HTML-style coverage report is generated and placed in
file:///tmp/topowiz-coverage/index.html.

To run 'style' tests to ensure all code complies with pep8 and other coding
standards:

    $ ./style_tests.sh

The code for the self-contained lambda function is located in the folder
topowiz/lambda_function.

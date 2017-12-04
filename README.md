# Romana TopoWiz: The topology wizard

## Installation

TopoWiz was developed on a Ubuntu 14.04 system. It should work on later
versions of Ubuntu as well. Developed with Python 3.4.3 and boto3.

Here are the steps to create a working environment locally:

1a. Install Python 3.6 on your older Linux system. This is only necessary if
    you don't have Python 3.6 on your system already, or can't just get it
    through the normal channels (apt-get update):

    $ sudo apt-get install software-properties-common
    $ sudo add-apt-repository ppa:deadsnakes/ppa
    $ sudo apt-get update
    $ sudo apt-get install python3.6

1b. Install some system-wide dependencies:

    $ sudo apt-get install python3-dev
    $ sudo apt-get install python3-pip
    $ sudo pip3 install --upgrade pip
    $ sudo pip3 install --upgrade virtualenvwrapper

2. Create a virtualenv for the project and change into it:

    $ virtualenv -p python3.6 topowiz
    $ cd topowiz
    $ source bin/activate
    $ pip3 install --upgrade setuptools
    $ pip3 install --upgrade pip

3. Clone/download the repository and step into the directory:

    $ git clone git@github.com:romana/topowiz.git
    $ cd topowiz

4. Deployment with Zappa

   Having AWS credentials environment variabls does NOT seem to work. It
   appears Zappa always uses credentials from ~/.aws/config

   Deploying the application:

    $ zappa init
    $ zappa deploy dev

5. For local development and testing:

    $ pip3 install -r requirements/develop.txt

    Set the Flask environment variable(s) and run the server:

    $ export FLASK_APP=topowiz/http.py
    $ export FLASK_DEBUG=1
    $ flask run


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

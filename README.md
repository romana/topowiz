# Romana TopoWiz: The topology wizard

## Installation

TopoWiz was developed for Linux / Python 3.6.3.

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

4. For local development and testing:

    $ pip3 install -r requirements/develop.txt

    Set the Flask environment variable(s) and run the server:

    $ export FLASK_APP=topowiz/http.py
    $ export FLASK_DEBUG=1
    $ flask run

    Note the FLASK_DEBUG setting: If this is not set then we'll serve static
    content out of an S3 bucket, which is invonvenient if you are experimenting
    with local changes. So, please make sure to have this environment variable
    set for local development.

5. Deployment with Zappa

   Having AWS credentials environment variabls does NOT seem to work. It
   appears Zappa always uses credentials from ~/.aws/config

   Static content needs to be uploaded to an S3 bucket. Please review
   topowiz/app_config.py for correctness.

   Uploading static content:

    $ ./s3_upload.py

   Deploying the application:

    $ zappa init
    $ zappa deploy dev


Developing
----------
To run all unit tests:

    $ ./run_tests.sh

An HTML-style coverage report is generated and placed in
file:///tmp/topowiz-coverage/index.html.

To run 'style' tests to ensure all code complies with pep8 and other coding
standards:

    $ ./style_tests.sh

"""
Copyright 2017 Pani Networks Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

import json
import urllib

from flask import Flask, render_template, request


app = Flask(__name__, static_url_path="/static")

QUESTION_LOOKUP = {
    "is_aws"     : "Where is your deployment?",
    "aws_region" : "Select the AWS region of your cluster:",
    "aws_zones"  : "Select one or more availability zones for the cluster:"
}


AWS_REGIONS = [
    "us-east-1",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "sa-east-1"
]


AWS_ZONES = {
    "us-east-1"      : ["us-east-1a", "us-east-1b", "us-east-1c",
                        "us-east-1d", "us-east-1e"],
    "us-west-1"      : ["us-west-1a", "us-west-1b"],
    "us-west-2"      : ["us-west-2a", "us-west-2b", "us-west-2c"],
    "eu-west-1"      : ["eu-west-1a", "eu-west-1b", "eu-west-1c"],
    "eu-central-1"   : ["eu-central-1a", "eu-central-1b"],
    "ap-southeast-1" : ["ap-southeast-1a", "ap-southeast-1b"],
    "ap-southeast-2" : ["ap-southeast-2a", "ap-southeast-2b",
                        "ap-southeast-2c"],
    "ap-northeast-1" : ["ap-northeast-1a", "ap-northeast-1c"],
    "sa-east-1"      : ["sa-east-1a", "sa-east-1b", "sa-east-1c"]
}


VALID_PARAMS = [
    ("is_aws",     bool),
    ("aws_region", str),
    ("aws_zones",  list)
]
VALID_PARAM_NAMES = [e[0] for e in VALID_PARAMS]
VALID_PARAM_TYPES = dict((e) for e in VALID_PARAMS)


def render_conf(conf):
    return json.dumps(conf, indent=4)


def conf_to_url(conf):
    return urllib.parse.quote_plus(json.dumps(conf))


@app.route('/', methods=['GET', 'POST'], defaults={'raw_path':''})
@app.route('/<path:raw_path>', methods=['GET', 'POST'])
def req(raw_path):
    if not raw_path:
        # No parameters? Render the welcome page...
        return render_template('welcome.html', conf_url=conf_to_url({}))

    error = None

    if raw_path == "init":
        # Starting the question dialog, empty config, no attempt to extract
        # config or parameters from URL.
        conf = {}
    else:
        try:
            conf = json.loads(urllib.parse.unquote_plus(raw_path))
        except:
            return render_template('error.html',
                                   error_msg = "Could not extract current "
                                               "configuration!")

        # Config extracted, now handling parameters. Every submission should
        # give us exactly one parameter value, or the same parameter value name
        # multiple times for a multi-select.
        if len(request.args) < 1:
            error = "Please fill in the form!"
        else:
            # URL parameters are in some weird immutable dict type. Easier to
            # work with if we convert the names to a list first.
            param_name_list = list(request.args.keys())
            # Normally, we only have a single parameter with each form
            # submission. Sometimes (in case of multi-select forms) the same
            # parameter name may appear multiple times, though. We look at the
            # first parameter name, lookup the type and go from there.
            param_name = param_name_list[0]
            if param_name in VALID_PARAM_NAMES:
                param_type = VALID_PARAM_TYPES[param_name]
                if param_type in [bool, str, int]:
                    value = param_type(request.args[param_name])
                elif param_type == list:
                    value = request.args.getlist(param_name)
                else:
                    return render_template(
                                'error.html',
                                error_msg = "Unsupported type for '%s'!" %
                                            param_name)
            else:
                return render_template('error.html',
                                       error_msg = "Invalid form parameter!")

            conf[param_name] = value

    # Look for the first missing value in the conf. That value's name is the
    # key for the question to ask (and form to display).
    question = None
    for v in VALID_PARAM_NAMES:
        if v not in conf:
            question = v
            break

    return render_template('main.html', conf_url=conf_to_url(conf),
                                        render_conf=render_conf(conf),
                                        conf=conf,
                                        question=question,
                                        qlookup=QUESTION_LOOKUP,
                                        aws_regions=AWS_REGIONS,
                                        aws_zones=AWS_ZONES,
                                        error=error)

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

import base64
import ipaddr
import json
import urllib

from flask     import Flask, render_template, request, redirect
from wtforms   import RadioField, SelectMultipleField, StringField, \
                      SubmitField, IntegerField, validators, widgets
from flask_wtf import FlaskForm


app = Flask(__name__, static_url_path="/static")
app.secret_key = 'development key'


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

HELP_TEXT_IS_AWS = \
    ("Topology configurations for data center and AWS deployments differ. It "
     "is therefore necessary to let the topology generator know where the "
     "Romana cluster runs.")

HELP_TEXT_AWS_REGIONS = \
    ("Topology configuration is specific to the AWS region and zones.")

HELP_TEXT_AWS_ZONES = \
    ("By letting the topology generator know the availability zones of "
     "cluster nodes, a topology can be constructed, which facilitates the "
     "automatic creation of 'prefix groups' (aggregated IP address spaces "
     "for endpoints on those nodes). The topology also will contain "
     "annotations that enable the automatic assignment of new cluster "
     "nodes to the correct prefix groups.")

HELP_TEXT_NETWORK = \
    ("A 'network' defines an address range from which Romana "
     "assign IP addresses to endpoints (such as pods or VMs). "
     "You can define more than one network. This is useful in those cases "
     "when you do not have one large, contiguous address range available "
     "to you, but only a few smaller ones. Romana will use all address "
     "ranges equally.<br>&nbsp;<br>"
     "You can provide a user friendly name to those "
     "networks to make it easier for you to keep track of them, or just "
     "accept the generated default name.<br>&nbsp;<br>"
     "The 'block mask size' is used by "
     "Romana's IPAM for an internal allocation unit. In most cases "
     "it is fine to leave it at the default of '29'. Use smaller values "
     "if you have very large numbers of endpoints on hosts to reduce the "
     "number of routes on hosts.")


def calculate_num_groups(conf, num_networks=None):
    """
    Calculates how many prefix groups we can have per zone. Takes into account
    that we need a route for each prefix group and we can't have more than 48
    route total.

    """
    num_zones  = len(conf['aws_zones'])
    num_nets   = len(conf['networks']) if num_networks is None else \
                                      num_networks
    num_groups = 32

    while num_groups * num_zones * num_nets > 48:
        if num_groups == 1:
            raise Exception("Too many networks and/or zones, reaching "
                            "50 route limit for AWS.")
        num_groups //= 2
    return num_groups


def build_topology(conf):
    topo = {"networks": [], "topologies" : []}
    for n in conf['networks']:
        topo["networks"].append(n)

    if conf['is_aws']:
        # Special casing the topology creation in VPC
        # - If just one zone, we need one group, since it's a flat network.
        # - If it's more than one zone, we want many groups per zone, but
        #   the total number of groups should not exceed 50 or even 40.
        # - We only have one topology if in VPC.
        t = {
            "networks" : [n['name'] for n in conf['networks']],
            "map"      : []
        }

        num_zones = len(conf['aws_zones'])

        if num_zones == 1:
            t["map"].append({
                "name"   : conf['aws_zones'][0],
                "groups" : []
            })
        else:
            num_groups = calculate_num_groups(conf)

            for zone in conf['aws_zones']:
                m = {
                    "name" : zone,
                    "assignment" : {"failure-domain" : zone},
                    "groups" : []
                }
                for i in range(num_groups):
                    m["groups"].append({
                        "name" : "%s-%02d" % (zone, i),
                        "groups" : []
                    })
                t["map"].append(m)

    else:
        # Routed DC network
        t = {
            "networks" : [n['name'] for n in conf.networks],
        }

        top_level_group_label = None
        if conf.dc_flat_net:
            if conf.dc_pg_per_host:
                num_groups = conf.dc_flat_net_num_hosts
                top_level_group_label = "host-%d"
            else:
                num_groups = 1
        else:
            num_groups = conf.dc_num_racks
            top_level_group_label = "rack-%d"

        m = []
        for i in range(num_groups):
            g = {"groups" : []}
            if top_level_group_label:
                g["name"] = top_level_group_label % i
            if not conf.dc_flat_net:
                g["assignment"] = {"rack" : g["name"]}
            m.append(g)

        if not conf.dc_flat_net:
            if conf.dc_pg_per_host:
                for top_level_group in m:
                    for i in range(conf.dc_num_hosts_per_rack):
                        g = {
                            "name" : "host-%d" % i,
                            "groups" : []
                        }
                        top_level_group["groups"].append(g)
        t["map"]  = m

    topo["topologies"].append(t)
    return topo


def render_conf(conf):
    return json.dumps(conf, indent=4)


def conf_to_url(conf):
    return urllib.parse.quote_plus(json.dumps(conf))


class IsAwsForm(FlaskForm):
    is_aws = RadioField('Where is your deployment?',
                        choices=[("aws", 'In an AWS VPC'),
                                 ("dc",  'In my own datacenter')])
    submit = SubmitField(label='Submit')


class AwsRegionForm(FlaskForm):
    aws_region = RadioField('Select the AWS region of your cluster:',
                            choices=[(r,r) for r in AWS_REGIONS],
                            validators=[validators.DataRequired()])
    submit = SubmitField(label='Submit')


class AddNetworkForm(FlaskForm):
    net_cidr   = StringField('Valid IPv4 CIDR for network address range:',
                             [validators.required()])
    net_name   = StringField('User friendly name of network:',
                             [validators.required()])
    block_mask = IntegerField('Block mask size:',
                              [validators.required(),
                               validators.NumberRange(
                                   message="Should be between 16 and 32",
                                   min=16, max=32)
                              ], default=29)
    submit     = SubmitField(label='Submit')
    cancel     = SubmitField(label="Done")

    def __init__(self, *args, **kwargs):
        self.conf = kwargs['conf']
        del kwargs['conf']
        super(AddNetworkForm, self).__init__(*args, **kwargs)

    def validate_net_cidr(self, field):
        """
        Custom validator for the CIDR field.

        """
        cidr    = field.data
        err_msg = "Not a valid CIDR"
        try:
            net, host = cidr.split("/")
            host = int(host)
            if host < 1 or host > 32:
                raise Exception()
            ipaddr.IPNetwork(cidr)
            other_cidrs = [n['cidr'] for n in self.conf.get('networks', [])]
            if cidr in other_cidrs:
                err_msg = "This CIDR is already in use."
                raise Exception()
            cidr_obj = ipaddr.IPNetwork(cidr)
            for other_cidr in other_cidrs:
                if cidr_obj.overlaps(ipaddr.IPNetwork(other_cidr)):
                    err_msg = "CIDR '%s' overlaps with existing CIDR '%s'" % \
                              (cidr, other_cidr)
                    raise Exception()
        except:
            raise validators.ValidationError(err_msg)

    def validate_net_name(self, field):
        """
        Custom validator for network name.

        """
        name = field.data
        other_names = [n['name'] for n in self.conf.get('networks', [])]
        if name and name in other_names:
            raise validators.ValidationError("This name is already in use.")


def get_conf(raw_conf):
    """
    Extract the raw configuration, return error if necessary.

    In case of error we return the readily rendered error template.

    """
    try:
        conf = json.loads(urllib.parse.unquote_plus(raw_conf))
        return conf, None
    except:
        return None, render_template(
                            'error.html',
                            error_msg = "Could not extract current "
                                        "configuration!")


@app.route('/', methods=['GET'])
def home():
    return render_template('welcome.html', conf_url=conf_to_url({}))


@app.route('/is_aws', methods=['GET', 'POST'])
def is_aws_view():
    """
    Asking whether this is an AWS or datacenter deployment.

    """
    form = IsAwsForm()

    if form.validate_on_submit():
        conf = { "is_aws" : form.is_aws.data == "aws" }
        if conf['is_aws']:
            return redirect('/aws/region/%s' % conf_to_url(conf))
        else:
            raise Exception("Not yet implemented!")

    return render_template('question.html',
                           form=form,
                           help_text=HELP_TEXT_IS_AWS,
                           action=request.path)


@app.route('/aws/region/<path:raw_conf>', methods=['GET', 'POST'])
def aws_region_view(raw_conf):
    """
    Asking for the AWS region in which the cluster is deployed.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    form = AwsRegionForm()

    if form.validate_on_submit():
        conf['aws_region'] = form.aws_region.data
        return redirect('/aws/zones/%s' % conf_to_url(conf))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_AWS_REGIONS,
                           action=request.path)


@app.route('/aws/zones/<path:raw_conf>', methods=['GET', 'POST'])
def aws_zones_view(raw_conf):
    """
    Asking for the AWS Zones in which the cluster is deployed.

    Note that our form is generated dynamically within this function here
    (closure), because the zones presented for selection depend on an earlier
    choice (the region).

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    class _AwsZonesForm(FlaskForm):
        # The zones form needs to be dynamically created, because the
        # zones depend on the chosen region. That's why it is defined here in
        # this function, rather with all the other forms.
        # Thank you to the explanation of how to get checkboxes with WTForms:
        # http://www.ergo.io/tutorials/persuading-wtforms/
        #                          persuading-wtforms-to-generate-checkboxes/
        aws_zones = SelectMultipleField(
                      'Select one or more availability zones for the cluster:',
                      choices=[(r,r) for r in AWS_ZONES[conf['aws_region']]],
                      validators=[validators.DataRequired()],
                      option_widget=widgets.CheckboxInput(),
                      widget=widgets.ListWidget(prefix_label=False)
                    )
        submit = SubmitField(label='Submit')

    form = _AwsZonesForm()

    if form.validate_on_submit():
        conf['aws_zones'] = form.aws_zones.data
        return redirect('/gen/nets/%s' % conf_to_url(conf))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_AWS_ZONES,
                           action=request.path)


@app.route('/gen/nets/<path:raw_conf>', methods=['GET', 'POST'])
def gen_networks(raw_conf):
    """
    Add networks to the config. This is called repeatedly in normal submit.

    User must press special button on form to break out of it.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    if "networks" not in conf:
        conf["networks"] = []

    num_networks = len(conf['networks'])

    try:
        # Test if we could handle one more network
        calculate_num_groups(conf, num_networks=num_networks+1)
    except:
        # Reached the limit...
        return redirect('/done/%s' % conf_to_url(conf))

    if request.method == "GET":
        form = AddNetworkForm(conf=conf, net_name="net-%d" % num_networks)
    else:
        form = AddNetworkForm(conf=conf)
        if form.cancel.data:
            # Processing the cancel button ahead of form validation, because we
            # want to allow it to be pressed even if form isn't filled out.
            return redirect('/done/%s' % conf_to_url(conf))

    if form.validate_on_submit():
        cidr       = form.net_cidr.data
        name       = form.net_name.data
        block_mask = form.block_mask.data
        conf["networks"].append({"cidr" : cidr, "name" : name,
                                 "block_mask" : block_mask})
        return redirect('/gen/nets/%s' % conf_to_url(conf))

    if num_networks == 0:
        table_title = "Provide information for a network:"
    else:
        table_title = "Provide information for additional network " \
                      "or press 'Done' button: "

    return render_template('add_network.html',
                           form=form,
                           table_title=table_title,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_NETWORK,
                           show_cancel=num_networks > 0,
                           action=request.path)


@app.route('/done/<path:raw_conf>', methods=['GET'])
def done(raw_conf):
    """
    Calculates the topology.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    topo = build_topology(conf)
    # Making a safe encoding for the URL. Note the 'decode' in the very end.
    # That's to remove the annoying   b'...'  formatting around the utf-8
    # encoded byte sequence.
    download_link = "/download/%s" % \
                    base64.urlsafe_b64encode(
                        conf_to_url(conf).encode("utf=8")).decode()

    return render_template('done.html',
                           topo=json.dumps(topo, indent=4),
                           render_conf=render_conf(conf),
                           download_link=download_link)


@app.route('/download/<path:raw_conf>', methods=['GET'])
def download(raw_conf):
    """
    Calculates the topology.

    """
    conf, err = get_conf(base64.urlsafe_b64decode(raw_conf).decode("utf-8"))
    if err:
        return err

    topo = build_topology(conf)
    response = app.response_class(
        response=json.dumps(topo, indent=4),
        status=200,
        mimetype='application/json'
    )
    return response
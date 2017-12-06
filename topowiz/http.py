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

from flask     import Flask, render_template, request, redirect, url_for
from wtforms   import RadioField, SelectMultipleField, StringField, \
                      SubmitField, IntegerField, validators, widgets
from flask_wtf import FlaskForm

from .topo     import calculate_num_groups, build_topology


app = Flask(__name__, static_url_path="/static")
app.secret_key = "secret key, which we don't really need for this"


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
     "Romana cluster is deployed.")

HELP_TEXT_AWS_REGIONS = \
    ("Topology configuration is specific to the AWS region and zones. "
     "Zones are specific to the AWS region the cluster is deployed in.")

HELP_TEXT_AWS_ZONES = \
    ("By letting the topology generator know the availability zones of "
     "cluster nodes, a topology can be constructed, which facilitates the "
     "automatic creation of 'prefix groups' (aggregated IP address spaces "
     "for endpoints on those nodes). The topology will contain "
     "annotations that enable the automatic assignment of new cluster "
     "nodes to the correct prefix groups.")

HELP_TEXT_NETWORK = \
    ("A 'network' defines an address range from which Romana "
     "assigns IP addresses to endpoints (such as pods or VMs). "
     "You can define more than one network. This is useful in those cases "
     "when you do not have one large, contiguous address range available, "
     "but only a few smaller ones. Define a network for each address range "
     "you are able to use for endpoint IPs. Romana will use all address "
     "ranges equally.<br>&nbsp;<br>"
     "You can provide a user friendly name to those "
     "networks to make it easier for you to keep track of them, or just "
     "accept the generated default name.")

HELP_TEXT_DC_OWN_PREFIX = \
    ("If this question is answered with 'Yes' then Romana's IPAM ensures "
     "that all endpoints assigned to a given host have the same address "
     "prefix. This is useful if routes need to be set in the network "
     "in order to reach endoints directly from outside the cluster: "
     "Giving each host its own "
     "unique address prefix for all endpoints means that only a "
     "single route needs to be configured in the network to make all "
     "endpoints on that host reachable.<br>&nbsp;<br>"
     "Note that this is usually only necessary if you have special "
     "requirements or restrictions on your network, since normally Romana "
     "sets routes directly on the cluster hosts to make endpoints reachable.")

HELP_TEXT_DC_FLAT_NET = \
    ("If all your hosts are located within the same L2 segment and they "
     "can all reach each other without intermittent routers or gateways "
     "then answer this question with 'Yes'.")

HELP_TEXT_DC_RACKS = \
    ("Information about the underlying network for your cluster, such as "
     "the maximum number of racks and (if required) the maximum number "
     "of hosts per rack. This is used by Romana's IPAM to calculate "
     "address prefix groups for efficient route aggregation.")

HELP_TEXT_DC_FLAT_NUM_HOSTS = \
    ("Since you selected to have a prefix group per host, Romana needs to "
     "know the maximum number of hosts you will have in your cluster.")


def render_conf(conf):
    """
    Provides the formatted version of the user config, which is displayed on
    the various question pages.

    """
    return json.dumps(conf, indent=4)


def conf_to_url(conf):
    """
    Provides a URL safe version of the config, which therefore can be included
    in each request.

    """
    return base64.urlsafe_b64encode(json.dumps(conf).encode("utf=8")).decode()


def get_conf(raw_conf):
    """
    Extract the configuration from the urlencoded version.

    Returns tuple of (conf, error)

    In case of error we return the readily rendered error template.
    If no error, then 'error' in the return tuple is None.

    """
    try:
        conf = json.loads(base64.urlsafe_b64decode(raw_conf).decode("utf-8"))
        return conf, None
    except Exception:
        return None, render_template(
                            'error.html',
                            error_msg = "Could not extract current "
                                        "configuration!")


# ------------------
# Forms
# ------------------

class IsAwsForm(FlaskForm):
    is_aws = RadioField('Where is your deployment?',
                        choices=[("aws", 'In an AWS VPC'),
                                 ("dc",  'In my own datacenter')])
    submit = SubmitField(label='Submit')


class DcOwnPrefixForm(FlaskForm):
    dc_pg_per_host = RadioField('Should each host have its own CIDR prefix '
                                'for endpoint addresses?',
                                 choices=[("yes", "Yes"), ("no", "No")],
                                 validators=[validators.DataRequired()])
    submit = SubmitField(label='Submit')


class DcFlatNetForm(FlaskForm):
    dc_flat_net = RadioField('Do you have a flat network in your data '
                             'center? Are all hosts on a single L2 segment?',
                              choices=[("yes", "Yes"), ("no", "No")],
                              validators=[validators.DataRequired()])
    submit = SubmitField(label='Submit')


class DcFlatNetNumHostsForm(FlaskForm):
    dc_flat_net_num_hosts = IntegerField(
                                'Maximum number of hosts in cluster?',
                                validators=[
                                    validators.DataRequired(),
                                    validators.NumberRange(
                                        message="Should be between 1 and 2048",
                                        min=1, max=2048)
                                ])
    submit = SubmitField(label='Submit')


class DcRacksForm(FlaskForm):
    dc_num_racks = IntegerField('Maximum number of racks in data center?',
                                validators=[
                                    validators.DataRequired(),
                                    validators.NumberRange(
                                        message="Should be between 1 and 256",
                                        min=1, max=256)
                                ])


class AwsRegionForm(FlaskForm):
    aws_region = RadioField('Select the AWS region of your cluster:',
                            choices=[(r, r) for r in AWS_REGIONS],
                            validators=[validators.DataRequired()])
    submit = SubmitField(label='Submit')


class AddNetworkForm(FlaskForm):
    net_cidr   = StringField('Valid IPv4 CIDR for network address range:',
                             [validators.required()])
    net_name   = StringField('User friendly name of network:',
                             [validators.required()])
    block_mask = IntegerField('Block mask size:',
                              default=29,
                              validators=[
                                  validators.required(),
                                  validators.NumberRange(
                                      message="Should be between 16 and 32",
                                      min=16, max=32)
                              ])
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
        except Exception:
            raise validators.ValidationError(err_msg)

    def validate_net_name(self, field):
        """
        Custom validator for network name.

        """
        name = field.data
        other_names = [n['name'] for n in self.conf.get('networks', [])]
        if name and name in other_names:
            raise validators.ValidationError("This name is already in use.")


# ------------------
# Views
# ------------------

@app.route('/', methods=['GET'])
def home():
    return render_template('welcome.html', conf_url=conf_to_url({}))


@app.route('/is_aws', methods=['GET', 'POST'])
def is_aws():
    """
    Asking whether this is an AWS or datacenter deployment.

    """
    form = IsAwsForm()

    if form.validate_on_submit():
        conf = {"is_aws" : form.is_aws.data == "aws"}
        if conf['is_aws']:
            return redirect(url_for('.aws_region', raw_conf=conf_to_url(conf)))
        else:
            return redirect(url_for('.dc_own_prefix',
                                    raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           help_text=HELP_TEXT_IS_AWS,
                           action=url_for('.is_aws'))


@app.route('/dc/own_prefix/<path:raw_conf>', methods=['GET', 'POST'])
def dc_own_prefix(raw_conf):
    """
    Ask if each host should have its own prefix group in a DC deployment.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    form = DcOwnPrefixForm()

    if form.validate_on_submit():
        conf['dc_pg_per_host'] = form.dc_pg_per_host.data == "yes"
        return redirect(url_for('.dc_flat_net', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_DC_OWN_PREFIX,
                           done="20%",
                           action=url_for('.dc_own_prefix',
                                          raw_conf=raw_conf))


@app.route('/dc/flat_net/<path:raw_conf>', methods=['GET', 'POST'])
def dc_flat_net(raw_conf):
    """
    Ask if we have a flat network in the data center.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    form = DcFlatNetForm()

    if form.validate_on_submit():
        conf['dc_flat_net'] = form.dc_flat_net.data == "yes"
        if conf['dc_flat_net']:
            if conf['dc_pg_per_host']:
                return redirect(url_for('.dc_flat_net_num_hosts',
                                        raw_conf=conf_to_url(conf)))
            else:
                return redirect(url_for('.gen_networks',
                                        raw_conf=conf_to_url(conf)))
        else:
            return redirect(url_for('.dc_racks', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_DC_FLAT_NET,
                           done="40%",
                           action=url_for('.dc_flat_net',
                                          raw_conf=raw_conf))


@app.route('/dc/racks/<path:raw_conf>', methods=['GET', 'POST'])
def dc_racks(raw_conf):
    """
    How many racks in a routed network?

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    class _DcRacksForm(DcRacksForm):
        pass

    if conf['dc_pg_per_host']:
        # Need to ask for number of hosts per rack only if a PG per host was
        # selected.
        dc_num_hosts_per_rack = IntegerField(
                                'Maximum number of hosts per rack?',
                                validators=[
                                    validators.DataRequired(),
                                    validators.NumberRange(
                                        message="Should be between 1 and 256",
                                        min=1, max=1024)
                                ])
        setattr(_DcRacksForm, "dc_num_hosts_per_rack", dc_num_hosts_per_rack)

    submit = SubmitField(label='Submit')
    setattr(_DcRacksForm, "submit", submit)

    form = _DcRacksForm()

    if form.validate_on_submit():
        conf['dc_num_racks'] = form.dc_num_racks.data
        if conf['dc_pg_per_host']:
            conf['dc_num_hosts_per_rack'] = form.dc_num_hosts_per_rack.data
        return redirect(url_for('.gen_networks', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_DC_RACKS,
                           table_title="Information about your data center "
                                       "racks:",
                           done="70%",
                           action=url_for('.dc_racks', raw_conf=raw_conf))


@app.route('/dc/flat_net_num_hosts/<path:raw_conf>', methods=['GET', 'POST'])
def dc_flat_net_num_hosts(raw_conf):
    """
    How many hosts if we are in a flat network?

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    form = DcFlatNetNumHostsForm()

    if form.validate_on_submit():
        conf['dc_flat_net_num_hosts'] = form.dc_flat_net_num_hosts.data
        return redirect(url_for('.gen_networks', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_DC_FLAT_NUM_HOSTS,
                           done="60%",
                           action=url_for('.dc_flat_net_num_hosts',
                                          raw_conf=raw_conf))


@app.route('/aws/region/<path:raw_conf>', methods=['GET', 'POST'])
def aws_region(raw_conf):
    """
    Asking for the AWS region in which the cluster is deployed.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    form = AwsRegionForm()

    if form.validate_on_submit():
        conf['aws_region'] = form.aws_region.data
        return redirect(url_for('.aws_zones', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_AWS_REGIONS,
                           done="30%",
                           action=url_for('.aws_region',
                                          raw_conf=raw_conf))


@app.route('/aws/zones/<path:raw_conf>', methods=['GET', 'POST'])
def aws_zones(raw_conf):
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
                      choices=[(r, r) for r in AWS_ZONES[conf['aws_region']]],
                      validators=[validators.DataRequired()],
                      option_widget=widgets.CheckboxInput(),
                      widget=widgets.ListWidget(prefix_label=False)
                    )
        submit = SubmitField(label='Submit')

    form = _AwsZonesForm()

    if form.validate_on_submit():
        conf['aws_zones'] = form.aws_zones.data
        return redirect(url_for('.gen_networks', raw_conf=conf_to_url(conf)))

    return render_template('question.html',
                           form=form,
                           render_conf=render_conf(conf),
                           help_text=HELP_TEXT_AWS_ZONES,
                           done="60%",
                           action=url_for('.aws_zones',
                                          raw_conf=raw_conf))


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

    if conf['is_aws']:
        try:
            # Test if we could handle one more network
            calculate_num_groups(conf, num_networks=num_networks + 1)
        except Exception:
            # Reached the limit...
            return redirect(url_for('.done', raw_conf=conf_to_url(conf)))

    if request.method == "GET":
        form = AddNetworkForm(conf=conf, net_name="net-%d" % num_networks)
    else:
        form = AddNetworkForm(conf=conf)
        if form.cancel.data:
            # Processing the cancel button ahead of form validation, because we
            # want to allow it to be pressed even if form isn't filled out.
            return redirect(url_for('.done', raw_conf=conf_to_url(conf)))

    if form.validate_on_submit():
        cidr       = form.net_cidr.data
        name       = form.net_name.data
        block_mask = form.block_mask.data
        conf["networks"].append({"cidr" : cidr, "name" : name,
                                 "block_mask" : block_mask})
        return redirect(url_for('.gen_networks', raw_conf=conf_to_url(conf)))

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
                           done="80%",
                           action=url_for('.gen_networks',
                                          raw_conf=raw_conf))


@app.route('/done/<path:raw_conf>', methods=['GET'])
def done(raw_conf):
    """
    Calculates and displayes the full topology.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    topo = build_topology(conf)
    # Making a safe encoding for the URL. Note the 'decode' in the very end.
    # That's to remove the annoying   b'...'  formatting around the utf-8
    # encoded byte sequence.
    download_link = url_for(".download", raw_conf=raw_conf)

    return render_template('done.html',
                           topo=json.dumps(topo, indent=4),
                           render_conf=render_conf(conf),
                           download_link=download_link)


@app.route('/download/<path:raw_conf>', methods=['GET'])
def download(raw_conf):
    """
    Serves the full topology in downloadable JSON format.

    """
    conf, err = get_conf(raw_conf)
    if err:
        return err

    topo = build_topology(conf)
    response = app.response_class(
        response=json.dumps(topo, indent=4),
        status=200,
        mimetype='application/json'
    )
    return response

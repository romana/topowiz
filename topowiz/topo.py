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

import ipaddr
import json
import sys


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


def _test_cidr(cidr):
    try:
        net, host = cidr.split("/")
        host = int(host)
        if host < 1 or host > 32:
            raise Exception()
        ipaddr.IPNetwork(cidr)
    except:
        raise Exception("Malformed CIDR '%s'" % cidr)


class Config(object):
    def __init__(self, initial_data=None):
        self.aws_is_in             = None
        self.aws_region            = None
        self.aws_is_multizone      = None
        self.aws_azs               = None
        self.dc_flat_net           = None
        self.dc_flat_net_num_hosts = None
        self.dc_pg_per_host        = None
        self.dc_num_racks          = None
        self.dc_num_hosts_per_rack = None
        self.networks              = None

        if initial_data:
            aws  = initial_data.get('aws')
            dc   = initial_data.get('datacenter')
            nets = initial_data.get('networks')

            if not nets:
                raise Exception("'networks' section missing from config")

            if aws is not None and dc is not None:
                raise Exception("Can only specify one of 'aws' or "
                                "'datacenter'")

            #
            # Check validity of network section
            #
            if type(nets) is not list:
                raise Exception("Expected list of networks")

            names         = []
            cidrs         = []
            self.networks = []
            for i, net in enumerate(nets):
                if type(net) is not dict:
                    raise Exception("Expected network defined as dict")
                name       = net.get("name", "net-%d" % i)
                cidr       = net.get("cidr")
                block_mask = net.get("block_mask", 29)
                _test_cidr(cidr)
                # Check that the name is unique
                if name in names:
                    raise Exception("Network name '%s' used more than once" %
                                    name)
                # Check that CIDRs don't overlap
                cidr_obj = ipaddr.IPNetwork(cidr)
                for other_cidr in cidrs:
                    if cidr_obj.overlaps(ipaddr.IPNetwork(other_cidr)):
                        raise Exception("CIDR '%s' overlaps with CIDR '%s'" %
                                        (cidr, other_cidr))
                # Check for valid block mask
                if not 16 <= block_mask <= 32:
                    raise Exception("Invalid block mask value (16 - 32)")

                cidrs.append(cidr)
                names.append(name)

                self.networks.append({
                    "name"       : name,
                    "cidr"       : cidr,
                    "block_mask" : block_mask
                })

            #
            # Check validity of AWS section
            #
            if aws:
                region = aws.get("region")
                zones  = aws.get("zones")
                if region not in AWS_REGIONS:
                    raise Exception("Unknown AWS region '%s'" % region)
                for z in zones:
                    if z not in AWS_ZONES[region]:
                        raise Exception("Invalid zone '%s' for region '%s'" %
                                        (z, region))
                self.aws_is_in        = True
                self.aws_region       = region
                self.aws_azs          = zones
                self.aws_is_multizone = len(zones) > 1

            #
            # Check validity of data center section
            #
            if dc:
                pg_per_host        = dc.get("prefix_per_host", False)
                flat_net           = dc.get("flat_network", False)
                flat_net_num_hosts = dc.get("num_hosts", 0)
                num_racks          = dc.get("num_racks", 0)
                num_hosts_per_rack = dc.get("num_hosts_per_rack", 0)

                if type(flat_net_num_hosts) is not int:
                    raise Exception("num_hosts needs to be an int")
                if type(num_racks) is not int:
                    raise Exception("num_racks needs to be an int")
                if type(num_hosts_per_rack) is not int:
                    raise Exception("num_hosts_per_rack needs to be an int")
                if type(pg_per_host) is not bool:
                    raise Exception("prefix_per_host needs to be a boolean")
                if type(flat_net) is not bool:
                    raise Exception("flat_network needs to be a boolean")

                if flat_net:
                    if num_racks:
                        raise Exception("Flat and routed network (multiple "
                                        "racks) cannot be requested at the "
                                        "same time.")
                    if num_hosts_per_rack:
                        raise Exception("Hosts per rack cannot be specified "
                                        "in a flat network configuration")
                    if pg_per_host and not flat_net_num_hosts:
                        raise Exception("The number of hosts ('num_hosts') "
                                        "needs to be specified if a prefix "
                                        "per host is requested")
                else:
                    if flat_net_num_hosts:
                        raise Exception("'num_hosts' cannot be specified "
                                        "for a routed network")
                    if not num_racks:
                        raise Exception("Number of racks needs to be "
                                        "specified for a routed (not flat) "
                                        "network")
                    if pg_per_host and not num_hosts_per_rack:
                        raise Exception("The number of hosts per rack "
                                        "('num_hosts_per_rack') needs to be "
                                        "specified if a prefix per host is "
                                        "requested")

                self.aws_is_in             = False
                self.dc_flat_net           = flat_net
                self.dc_flat_net_num_hosts = flat_net_num_hosts
                self.dc_pg_per_host        = pg_per_host
                self.dc_num_racks          = num_racks
                self.dc_num_hosts_per_rack = num_hosts_per_rack


    def pr(self, text, indent=50):
        print(" "*indent, text)


    def dump(self):
        print()
        self.pr("Current configuration:")
        if self.aws_is_in is not None:
            if self.aws_is_in:
                self.pr("- Cluster is in AWS VPC.")
            else:
                self.pr("- Cluster in datacenter (not in AWS VPC).")
        if self.aws_region is not None:
            self.pr("- In AWS region: %s" % self.aws_region)
        if self.aws_is_multizone is not None:
            if self.aws_is_multizone:
                self.pr("- This is a multi-zone cluster")
            else:
                self.pr("- This is NOT a multi-zone cluster")
        if self.aws_azs is not None:
            if len(self.aws_azs) > 1:
                self.pr("- Cluster in these zone(s): %s" %
                        ", ".join(self.aws_azs))
            else:
                self.pr("- Cluster in this zone: %s" % self.aws_azs[0])
        if self.dc_flat_net:
            self.pr("- Cluster hosts are in a flat network")
        if self.dc_flat_net_num_hosts:
            self.pr("- There are %d hosts in the flat network" %
                    self.dc_flat_net_num_hosts)
        if self.dc_pg_per_host:
            self.pr("- Every host gets a unique prefix for endpoint "
                    "addresses.")
        if self.dc_num_racks:
            self.pr("- There are at most %d racks in the data center" %
                    self.dc_num_racks)
        if self.dc_num_hosts_per_rack:
            self.pr("- There are at most %d hosts per rack" %
                    self.dc_num_hosts_per_rack)
        if self.networks:
            self.pr("- Networks: %s" %
                    ", ".join(["%s={CIDR:%s, block:%d}" %
                               (c['name'], c['cidr'], c['block_mask'])
                               for c in self.networks]))
        print()



def ask_yesno(conf, text):
    while True:
        x = input("%s (yes/no) " % text).strip().lower()
        if x in ["y", "t", "yes", "true"]:
            return True
        elif x in ["n", "f", "no", "false"]:
            return False
        print("   !!! Invalid input! Please answer 'yes' or 'no' !!!")


def ask_number(conf, text, min_val=None, max_val=None):
    while True:
        x = input("%s (%d - %d) " % (text, min_val, max_val))
        try:
            x = int(x)
            if x < min_val or x > max_val:
                raise
            return x
        except:
            print("   !!! Invalid number !!!")


def ask_name(conf, text):
    pass


def ask_network(conf, text):
    print(text)

    while True:
        name = input("- Name of the network: ")
        if len(name) < 1:
            print("   !!! Invalid network name !!!")
            continue
        if conf.networks:
            if name in [c['name'] for c in conf.networks]:
                print("   !!! This network name is already in use !!!")
                continue
        break

    while True:
        cidr = input("- CIDR of the network: ")
        try:
            net, host = cidr.split("/")
            host = int(host)
            if host < 1 or host > 32:
                raise
            n = ipaddr.IPNetwork(cidr)
            if conf.networks:
                if any([n.overlaps(ipaddr.IPNetwork(c['cidr']))
                        for c in conf.networks]):
                    print("!!! This CIDR overlaps another network's CIDR !!!")
                    continue
            break
        except:
            print("   !!! Invalid network CIDR !!!")

    while True:
        block_mask = input("- Romana address block mask "
                           "(16 - 32, default: 29): ")
        if not block_mask.strip():
            block_mask = 29
            break

        try:
            block_mask = int(block_mask)
            if block_mask > 32 or block_mask < 16:
                raise
            break
        except:
            print("   !!! Invalid address block mask !!!")

    return {
        "name"       : name,
        "cidr"       : cidr,
        "block_mask" : block_mask
    }


def ask_choice(conf, text, choices):
    min_val = 1
    max_val = len(choices)
    while True:
        print(text)
        for i, c in enumerate(choices):
            print("    %d. %s" % (i+1, c))
        try:
            x = int(input("Your selection (number between %d and %d): " %
                          (min_val, max_val)))
            if x < min_val or x > max_val:
                raise
            return choices[x-1]
        except:
            print("    !!! Please enter an number between %d and %d !!!" %
                  (min_val, max_val))


def ask_choice_list(conf, text, choices):
    return [ask_choice(text, choices)]


def ask_multichoice(conf, text, choices):
    min_val = 1
    max_val = len(choices)
    while True:
        print(text)
        for i, c in enumerate(choices):
            print("    %d. %s" % (i+1, c))
        try:
            xs = input("Your selection (comma separated list of numbers "
                       "between %d and %d): " % (min_val, max_val))
            raw_choices = [int(x) for x in xs.split(",")]
            for x in raw_choices:
                if x < min_val or x > max_val:
                    raise
            return [choices[x-1] for x in raw_choices]
        except:
            print("    !!! Please enter a comma separated list of numbers "
                  "between %d and %d !!!" % (min_val, max_val))


def ask_multi_net(conf, text, next_text):
    print(text)
    while True:
        net = ask_network(conf,
                          "Provide name, CIDR and block-size for new network:")
        if conf.networks is None:
            conf.networks = [net]
        else:
            conf.networks.append(net)
        if not ask_yesno(conf, next_text):
            break
    return conf.networks


def ask(conf, conf_attr, ask_func, *args, **kwargs):
    val = getattr(conf, conf_attr)
    if val is None:
        val = ask_func(conf, *args, **kwargs)
        setattr(conf, conf_attr, val)
        conf.dump()


def ask_questions(conf):
    ask(conf, "aws_is_in", ask_yesno,
        "Is the cluster in an AWS VPC?")

    if conf.aws_is_in:
        # Ask questions for VPC deployments
        ask(conf, "aws_region", ask_choice,
            "Select the AWS region:", AWS_REGIONS)
        ask(conf, "aws_is_multizone", ask_yesno,
            "Does the cluster stretch across multiple zones?")
        if conf.aws_is_multizone:
            ask(conf, "aws_azs", ask_multichoice,
                "Select the availability zones:", AWS_ZONES[conf.aws_region])
        else:
            ask(conf, "aws_azs", ask_choice_list,
                "Select the availability zone:", AWS_ZONES[conf.aws_region])
    else:
        # Ask questions for DC deployments
        ask(conf, "dc_pg_per_host",  ask_yesno,
            "Do you want each host to have its own prefix for endpoints?")
        ask(conf, "dc_flat_net", ask_yesno,
            "Do you have a flat network for hosts?")

        if conf.dc_flat_net:
            # For a flat host network
            if conf.dc_pg_per_host:
                ask(conf, "dc_flat_net_num_hosts", ask_number,
                    "Maximum number of hosts in cluster?",
                    min_val=1, max_val=2048)
        else:
            # For a routed DC network
            ask(conf, "dc_num_racks", ask_number,
                "Maximum number of racks in data center?",
                min_val=1, max_val=256)

            if conf.dc_pg_per_host:
                ask(conf, "dc_num_hosts_per_rack", ask_number,
                    "Maximum number of hosts in rack?",
                    min_val=1, max_val=1024)

    ask(conf, "networks", ask_multi_net,
        "Specify a network:",
        next_text="Add another network?")


def build_topology(conf):
    topo = {"networks": [], "topologies" : []}
    for n in conf.networks:
        topo["networks"].append(n)

    if conf.aws_is_in:
        # Special casing the topology creation in VPC
        # - If just one zone, we need one group, since it's a flat network.
        # - If it's more than one zone, we want many groups per zone, but
        #   the total number of groups should not exceed 50 or even 40.
        # - We only have one topology if in VPC.
        t = {
            "networks" : [n['name'] for n in conf.networks],
            "map"      : []
        }

        if len(conf.aws_azs) == 1:
            t["map"].append({
                "name"   : conf.aws_azs[0],
                "groups" : []
            })
        else:
            if len(conf.aws_azs) == 2:
                num_groups = 16
            elif len(conf.aws_azs) == 3:
                num_groups = 8
            else:
                num_groups = 4

            if num_groups * len(conf.aws_azs) * len(conf.networks) > 48:
                raise Exception("Too many networks and/or zones, raching "
                                "50 route limit for AWS.")

            for zone in conf.aws_azs:
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

def main():
    print()
    print("Romana topology wizard, v0.1.0")
    print()

    if len(sys.argv) > 1:
        fname = sys.argv[1]
        print("Reading simplified configuration from: %s" % fname)
        try:
            with open(fname, "r") as f:
                data_str = f.read()
            data = json.loads(data_str)
        except Exception as e:
            print("!!! Error loading configuration: %s" % str(e))
            sys.exit(1)
    else:
        data = None

    try:
        conf = Config(data)
    except Exception as e:
        print("!!! Error parsing configuration: %s" % str(e))
        sys.exit(1)

    ask_questions(conf)

    try:
        topo = build_topology(conf)
    except Exception as e:
        print("!!! Error building topology: %s" % str(e))
        sys.exit(1)

    print()
    print(json.dumps(topo, indent=4))

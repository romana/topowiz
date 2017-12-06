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

#
# Functions for the calculation of a full Romana topology from the simplified
# user configuration.
#


def calculate_num_groups(conf, num_networks=None):
    """
    Calculates how many prefix groups we can have per AWS zone. Takes into
    account that we need a route for each prefix group and we can't have more
    than 48 route total.

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


def _build_aws_topology(conf):
    """
    Build a topology for am AWS VPC deployment.

    """
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
    return t


def _build_dc_topology(conf):
    """
    Build a topology for a routed data center network.

    """
    t = {
        "networks" : [n['name'] for n in conf['networks']],
    }

    top_level_group_label = None
    if conf['dc_flat_net']:
        if conf['dc_pg_per_host']:
            num_groups = conf['dc_flat_net_num_hosts']
            top_level_group_label = "host-%d"
        else:
            num_groups = 1
    else:
        num_groups = conf['dc_num_racks']
        top_level_group_label = "rack-%d"

    m = []
    for i in range(num_groups):
        g = {"groups" : []}
        if top_level_group_label:
            g["name"] = top_level_group_label % i
        if not conf['dc_flat_net']:
            g["assignment"] = {"rack" : g["name"]}
        m.append(g)

    if not conf['dc_flat_net']:
        if conf['dc_pg_per_host']:
            for top_level_group in m:
                for i in range(conf['dc_num_hosts_per_rack']):
                    g = {
                        "name" : "host-%d" % i,
                        "groups" : []
                    }
                    top_level_group["groups"].append(g)
    t["map"]  = m

    return t


def build_topology(conf):
    """
    From the user provided configuration, calculate the full topology config.

    """
    topo = {"networks": [], "topologies" : []}
    for n in conf['networks']:
        topo["networks"].append(n)

    if conf['is_aws']:
        t = _build_aws_topology(conf)
    else:
        t = _build_dc_topology(conf)

    topo["topologies"].append(t)
    return topo

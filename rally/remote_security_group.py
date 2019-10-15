#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from rally.common import logging
from rally.common import utils

from rally.common import validation
from rally.task import context

from rally_openstack import consts
from rally_openstack import osclients
from rally_openstack.wrappers import network as network_wrapper


LOG = logging.getLogger(__name__)


def _prepare_remote_sg(user, secgroup_name):
    neutron = osclients.Clients(user['credential']).neutron()
    security_groups = neutron.list_security_groups()["security_groups"]
    rally_open = [sg for sg in security_groups if sg["name"] == secgroup_name]
    if not rally_open:
        descr = "remote_sg needed by some tests"
        rally_open = neutron.create_security_group(
            {"security_group": {"name": secgroup_name,
                                "tenant_id": user['tenant_id'], 
                                "description": descr}})["security_group"]
    else:
        rally_open = rally_open[0]

    rules_to_add = [
        {
            "protocol": "tcp",
            "port_range_max": 65535,
            "port_range_min": 1,
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress"
        },
        {
            "protocol": "udp",
            "port_range_max": 65535,
            "port_range_min": 1,
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress"
        },
        {
            "protocol": "icmp",
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress"
        }
    ]

    def rule_match(criteria, existing_rule):
        return all(existing_rule[key] == value
                   for key, value in criteria.items())

    for new_rule in rules_to_add:
        if not any(rule_match(new_rule, existing_rule) for existing_rule
                   in rally_open.get("security_group_rules", [])):
            new_rule["security_group_id"] = rally_open["id"]
            neutron.create_security_group_rule(
                {"security_group_rule": new_rule})

    return rally_open


@validation.add("required_platform", platform="openstack", admin=True,
                users=False)
@context.configure(name="remote_security_group", platform="openstack", order=370)
class RemoteScurityGroup(context.Context):
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "create_ports": {
               "description": "Create ports in remote sg?",
               "type": "boolean",
            },
            "num_of_ports": {
                "type": "integer",
                "description": "Num of ports to create"
            },
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "create_ports": True,
        "num_of_ports": 20,
    }


    def setup(self):
        self.ports = []
        net_wrapper = network_wrapper.wrap(
            osclients.Clients(self.context["admin"]["credential"]),
            self, config=self.config)
        for user, tenant_id in (utils.iterate_per_tenants(
                self.context.get("users", []))):
            # Generate FAKE SG that would only have some fake ports.
            sg_name = 'sg-remote-%s' % tenant_id
            self.remote_sg = _prepare_remote_sg(user, sg_name) 
            if not self.config.get('create_ports'):
                break
            neutron =  osclients.Clients(user['credential']).neutron()
            for i in range(0, self.config['num_of_ports']):
                port = {'port': {
                    'name': "remote_sg_port-%i" % i,
                    'security_groups': [self.remote_sg['id']],
                    'network_id': self.context["tenants"][tenant_id]["networks"][0]['id']}}
                self.ports.append(neutron.create_port(port))
        
    def cleanup(self):
        for user, tenant_id in utils.iterate_per_tenants(
                self.context["users"]):
            with logging.ExceptionLogger(
                    LOG,
                    "Unable to delete security group: %s."
                    % user["secgroup"]["name"]):
                clients = osclients.Clients(user["credential"])
                for port in self.ports:
                    clients.neutron().delete_port(port['id'])
                clients.neutron().delete_security_group(user["secgroup"]["id"])
                clients.neutron().delete_security_group(self.remote_sg['id'])

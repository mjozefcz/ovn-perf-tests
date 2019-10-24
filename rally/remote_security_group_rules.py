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


def _prepare_rules(user, remote_sg, num_of_rules):
    neutron = osclients.Clients(user['credential']).neutron()
    remote_sg = neutron.list_security_groups(name=remote_sg)['security_groups'][0]['id']
    rules_to_add = [
        {
            "protocol": "tcp",
            "port_range_min": 81 + 10 * i,
            "port_range_max": 85 + 10 * i,
            "remote_group_id": remote_sg,
            "direction": "ingress"
        } for i in range(0, num_of_rules)
    ]
    for rule in rules_to_add:
        rule["security_group_id"] = user['secgroup']['id']
        neutron.create_security_group_rule(
            {"security_group_rule": rule})


@validation.add("required_platform", platform="openstack", admin=True,
                users=False)
@context.configure(name="remote_security_group_rules", platform="openstack", order=373)
class RemoteScurityGroupRules(context.Context):
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "create_remote_rules": {
               "description": "Create rules in sg?",
               "type": "boolean",
            },
            "num_of_rules": {
               "description": "Number of rules to create",
               "type": "integer",
            },
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "create_remote_rules": True,
        "num_of_rules": True,
    }


    def setup(self):
        net_wrapper = network_wrapper.wrap(
            osclients.Clients(self.context["admin"]["credential"]),
            self, config=self.config)
        for user, tenant_id in (utils.iterate_per_tenants(
                self.context.get("users", []))):
            remote_sg_name = 'sg-remote-%s' % tenant_id
            _prepare_rules(user, remote_sg_name, self.config['num_of_rules']) 

    def cleanup(self):
        pass

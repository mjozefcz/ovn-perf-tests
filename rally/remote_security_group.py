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

import time

from rally.common import logging
from rally.common import utils
from rally.common import sshutils

from rally.common import validation
from rally.task import context
from rally.task import atomic

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

    # Where to bind ports. change if needed.
    COMPUTE_HOST='compute-1.redhat.local'
    COMPUTE_IP='192.168.24.8'

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


    def bind_port(self, port, subnet, neutron_client):
        port_id = port['port']['id']
        port_ip = port['port']['fixed_ips'][0]['ip_address']
        port_mac = port['port']['mac_address']
        gw_ip = subnet['subnet']['gateway_ip']
        mask = subnet['subnet']['cidr'].split('/')[1]
        name = "b_%s" % port_id[:8]

        param_dict = {'name': name, 'port_id': port_id, 'port_ip': port_ip,
                      'port_mac': port_mac, 'gw_ip': gw_ip, 'mask': mask}

        # Open SSH Connection
        ssh = sshutils.SSH('heat-admin', RemoteScurityGroup.COMPUTE_IP)

        # Check for connectivity
        ssh.wait(120, 1)

        commands = [
            "sudo ovs-vsctl add-port br-int %(name)s -- set Interface %(name)s type=internal -- set Interface %(name)s external_ids:iface-id=%(port_id)s external_ids:iface-status='active' external_ids:attached-mac=%(port_mac)s",
            "sudo ip netns add %(name)s",
            "sudo ip link set %(name)s netns %(name)s",
            "sudo ip netns exec %(name)s ip link set %(name)s address %(port_mac)s",
            "sudo ip netns exec %(name)s ip addr add %(port_ip)s/%(mask)s dev %(name)s",
            "sudo ip netns exec %(name)s ip link set %(name)s up",
            "sudo ip netns exec %(name)s ip route add default via %(gw_ip)s"]

        for c in commands:
            ssh.run(c % param_dict)

        self._wait_for_port_active(neutron_client, port_id)


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
            subnet_id = self.context["tenants"][tenant_id]["networks"][0]['subnets'][0]
            subnet = neutron.show_subnet(subnet_id)
            for i in range(0, self.config['num_of_ports']):
                port = {'port': {
                    'binding:host_id': RemoteScurityGroup.COMPUTE_HOST,
                    'name': "remote_sg_port-%i" % i,
                    'security_groups': [self.remote_sg['id']],
                    'network_id': self.context["tenants"][tenant_id]["networks"][0]['id']}}
                port = neutron.create_port(port)
                self.bind_port(port, subnet, neutron)
                self.ports.append(port)
        
    @atomic.action_timer("neutron._wait_for_port_active")
    def _wait_for_port_active(self, neutron_client, port_id):
        timeout = time.time() + 300 # 300 seconds
        while True:
            port = neutron_client.show_port(port_id)
            if port['port']['status'] == 'ACTIVE':
                break
            elif time.time() > timeout:
                raise Exception("Timeout waiting for port %s to become "
                                "ACTIVE" % port['port']['id'])
            time.sleep(3)

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

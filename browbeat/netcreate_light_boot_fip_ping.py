#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import random
import time
from oslo_concurrency import lockutils

from rally.common import sshutils
from rally_openstack import consts
from rally_openstack.scenarios.neutron import utils as neutron_utils
from rally_openstack.scenarios.vm import utils as vm_utils
from rally.task import atomic
from rally.task import scenario
from rally.task import types
from rally.task import validation


@types.convert(image={"type": "glance_image"}, flavor={"type": "nova_flavor"})
@validation.add("image_valid_on_flavor", flavor_param="flavor", image_param="image")
@validation.add("required_services", services=[consts.Service.NEUTRON, consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["neutron", "nova"], "keypair@openstack": {},
                             "allow_ssh@openstack": None},
                    name="BrowbeatPlugin.create_network_light_boot_ping", platform="openstack")
class CreateNetworkLightBootPing(neutron_utils.NeutronScenario, vm_utils.VMScenario):

    def run(self, image, flavor, ext_net_id, num_vms=1, router_create_args=None,
            network_create_args=None, subnet_create_args=None, **kwargs):
        ext_net_name = None
        if ext_net_id:
            ext_net_name = self.clients("neutron").show_network(
                ext_net_id)["network"]["name"]
        router_create_args["name"] = self.generate_random_name()
        router_create_args["tenant_id"] = self.context["tenant"]["id"]
        router_create_args.setdefault("external_gateway_info",
                                      {"network_id": ext_net_id, "enable_snat": True})
        router = self._create_router(router_create_args)

        network = self._create_network(network_create_args or {})
        subnet = self._create_subnet(network, subnet_create_args or {})
        self._add_interface_router(subnet['subnet'], router['router'])
        kwargs["nics"] = [{'net-id': network['network']['id']}]
        secgroup = self.context.get("user", {}).get("secgroup")

        for i in range(num_vms):
            # HACK_START
            host_id, host_ip = self._schedule()

            #ext_net = self.admin_clients("neutron").show_network(ext_net_id)
            fip = self._create_floatingip(ext_net_id)

            port_args = {'binding:host_id': host_id,
                         'security_groups': [secgroup["id"]]}
            port = self._create_port(network, port_args)
            self._associate_fip(floatingip=fip['floatingip'], port=port['port'])

            port_id = port['port']['id']
            port_ip = port['port']['fixed_ips'][0]['ip_address']
            port_mac = port['port']['mac_address']
            gw_ip = subnet['subnet']['gateway_ip']
            mask = subnet['subnet']['cidr'].split('/')[1]
            name = "b_%s" % port_id[:8]

            param_dict = {'name': name, 'port_id': port_id, 'port_ip': port_ip,
                          'port_mac': port_mac, 'gw_ip': gw_ip, 'mask': mask}

            # Open SSH Connection
            ssh = sshutils.SSH('heat-admin', host_ip)

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

            self._wait_for_port_active(port_id)
            self._wait_for_ping(fip['floatingip']['floating_ip_address'])

    @atomic.action_timer("neutron._associate_fip")
    def _associate_fip(self, floatingip, port):
        return self.admin_clients("neutron").update_floatingip(
            floatingip["id"],
            {"floatingip": {"port_id": port["id"]}})["floatingip"]

    def _schedule(self):
        # TODO: pull the available hypervisors via API
        hypervisors = {'compute-0.redhat.local': '192.168.24.9',
                       'compute-1.redhat.local': '192.168.24.8',
                       'compute-2.redhat.local': '192.168.24.30'}
        hpv = random.choice(list(hypervisors))
        return (hpv, hypervisors[hpv])

    @atomic.action_timer("neutron._wait_for_port_active")
    def _wait_for_port_active(self, port_id):
        timeout = time.time() + 300 # 300 seconds
        while True:
            port = self.clients("neutron").show_port(port_id)
            if port['port']['status'] == 'ACTIVE':
                break
            elif time.time() > timeout:
                raise Exception("Timeout waiting for port %s to become "
                                "ACTIVE" % port['port']['id'])
            time.sleep(3)

    @atomic.action_timer("neutron.create_router")
    def _create_router(self, router_create_args):
        """Create neutron router.

        :param router_create_args: POST /v2.0/routers request options
        :returns: neutron router dict
        """
#        return self.clients(
#            "neutron").create_router({"router": router_create_args})
        return self.admin_clients("neutron").create_router({"router": router_create_args})

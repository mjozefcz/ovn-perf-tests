#!/bin/bash
neutron floatingip-list  | awk {'print $2'}|xargs -P16 -i sh -c 'neutron floatingip-disassociate {} | neutron floatingip-delete {}'

for router in $(neutron router-list | grep rally| awk {'print $2'}| shuf); do
    for subnet in $(neutron router-port-list ${router}| grep subnet_id | grep -E "\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b" -o); do
        neutron router-interface-delete ${router} ${subnet} &
        neutron port-delete ${subnet} &
    done
    neutron router-delete ${router} &
done
neutron port-list | awk {'print $2'} |xargs -I% -P 16  neutron port-delete %
neutron security-group-list | grep -E  "(sg-remote|rally)" |  awk {'print $2'} | xargs -I% -P8 neutron security-group-delete %
openstack network list | grep rally | awk {'print $2'} | xargs -P8 -I% neutron net-delete %

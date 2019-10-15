#!/bin/bash
for router in $(neutron router-list | grep rally| awk {'print $2'}); do
    for subnet in $(neutron router-port-list ${router}| grep subnet_id | grep -E "\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b" -o); do
        neutron router-interface-delete ${router} ${subnet}
        neutron port-delete ${subnet}
    done
    neutron router-delete ${router}
done
neutron security-group-list | grep -E  "(sg-remote|rally)" |  awk {'print $2'} | xargs -I% neutron security-group-delete %
neutron net-list | grep rally | awk {'print $2'} | xargs neutron net-delete

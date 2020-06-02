#!/bin/bash
timestamp=$(date +%s)
ovn-sbctl list Logical_Flow > logical_flows.txt

num_of_fips=$(ovn-nbctl list nat |grep dnat_and_snat | wc -l)
num_of_lports=$(ovn-nbctl list logical_switch_port | grep uuid | wc -l)
num_of_routers=$(ovn-nbctl list logical_router | grep uuid | wc -l)
num_of_mac_bindings=$(ovn-sbctl list mac_binding | grep uuid | wc -l)
num_of_port_bindings=$(ovn-sbctl list port_binding | grep uuid | wc -l)
num_of_lflows=$(wc -l logical_flows.txt | awk {'print $1'})


# Retrieve all the stages in the current pipeline
grep ^external_ids logical_flows.txt | sed 's/.*stage-name=//' | tr -d '}' | tr -d '\"' | sort | uniq > stage_names.txt                                                                                                                       

# Count how many flows on each stage
while read stage; do echo $stage: $(grep $stage logical_flows.txt -c); done < stage_names.txt  > logical_flows_distribution.txt                                                                                                               

sort  -k 2 -g -r logical_flows_distribution.txt  > logical_flows_distribution_sorted.txt

mkdir -p results
mv logical_flows_distribution_sorted.txt results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                                       
echo "" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt
echo "num_of_lports: ${num_of_lports}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                                      
echo "num_of_mac_bindings: ${num_of_mac_bindings}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                          
echo "num_of_port_bindings: ${num_of_port_bindings}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                        
echo "num_of_routers: ${num_of_routers}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                                    
echo "num_of_fips: ${num_of_fips}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt
echo "num_of_lflows: ${num_of_lflows}" >> results/logical_flows_distribution_sorted-${timestamp}-fips:${num_of_fips}.txt                                                                                                                      

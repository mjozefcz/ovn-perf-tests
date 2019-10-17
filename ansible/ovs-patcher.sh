#!/bin/bash
FILE_TO_PATCH="/usr/bin/ovn-controller"

# get offset from file - if symbols are there
#offset=$(objdump -S ${FILE_TO_PATCH} |grep -A 3 'interval >= 1000' | grep cmp | awk {'print $1'} | sed 's/://g' | tr "[:lower:]" "[:upper:]")
# get offset from without symbols:
#offset=$(objdump -S ${FILE_TO_PATCH} | grep -w cmp | grep '$0x3e7' | grep -E '48 81 \w\w e7 03 00 00' | awk {'print $1'} | sed 's/://g' | tr "[:lower:]" "[:upper:]")
# or 
offset=$(docker exec ovn_controller objdump -S ${FILE_TO_PATCH} | grep -A3 -B3 -E 'cmp[[:space:]]+\$0x3e7' |grep -A1 sub | grep -w cmp |  awk {'print $1'} | sed 's/://g' | tr "[:lower:]" "[:upper:]")
# https://github.com/openvswitch/ovs/blob/master/lib/timeval.c#L674
# add +3 bytes, to be on 1000 value byte
offset=$(echo "obase=10; ibase=16; ${offset}" | bc)
offset=$((offset + 3))
# Write new value
# Longer than 99ms
#echo -n -e '\x63\x00' | docker exec -i ovn_controller dd of=${FILE_TO_PATCH} obs=1 seek=${offset} conv=notrunc
# Longer than 9ms
echo -n -e '\x09\x00' | docker exec -i ovn_controller dd of=${FILE_TO_PATCH} obs=1 seek=${offset} conv=notrunc

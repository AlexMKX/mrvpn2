#!/bin/bash

set -euo pipefail

IFS=", "

interfaces=()

for interface in $MRVPN_INTERFACES; do
 while ! ip link show "$interface" >/dev/null 2>&1; do
     echo "Waiting for interface $interface to come up..."
     sleep 1
 done
 interfaces+=("$interface")
done
IFS=', '
echo "Interfaces $MRVPN_INTERFACES are up."
TABLE="dns-redir"
my_ip=$(ip -j ro get 1.1.1.1 | jq -r ".[0].prefsrc")
echo "My IP is $my_ip"
sudo nft add table ip $TABLE
sudo nft flush table ip $TABLE
sudo nft add chain ip $TABLE prerouting '{ type nat hook prerouting priority dstnat; policy accept; }'
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} udp dport 53 counter dnat to "$my_ip":5301
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} tcp dport 53 counter dnat to "$my_ip":5301

/usr/local/sbin/pdns_recursor-startup "$@"

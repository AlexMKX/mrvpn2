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

# Attempt to download the latest DoH blocklist
curl -s https://raw.githubusercontent.com/dibdot/DoH-IP-blocklists/refs/heads/master/doh-ipv4.txt -o /doh-ipv4-new.txt

# Check if the download was successful and the file is not empty, otherwise use the fallback
if [ ! -s /doh-ipv4-new.txt ]; then
    echo "Failed to download or empty file, using fallback..."
    cp /doh-ipv4.txt /doh-ipv4-new.txt
fi

# Process the blocklist and apply nftables rules
sed 's/\s.*//' /doh-ipv4-new.txt | while read ip; do
    nft add rule ip dns-redir prerouting iif "wg-firezone" ip daddr $ip tcp dport 443 counter drop
    nft add rule ip dns-redir prerouting iif "wg-tik" ip daddr $ip tcp dport 443 counter drop
done

/usr/local/sbin/pdns_recursor-startup "$@"

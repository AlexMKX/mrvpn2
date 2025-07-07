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

# Block Google DNS DOH
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} ip daddr 8.8.8.8 tcp dport 443 counter drop
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} ip daddr 8.8.4.4 tcp dport 443 counter drop

# Block Cloudflare DNS DOH
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} ip daddr 1.1.1.1 tcp dport 443 counter drop
sudo nft add rule ip $TABLE prerouting iif \{ "${interfaces[*]}" \} ip daddr 1.0.0.1 tcp dport 443 counter drop

# Commented out DOH blocklist download and processing
#DOH_BLOCKLIST_URL="https://raw.githubusercontent.com/dibdot/DoH-IP-blocklists/refs/heads/master/doh-ipv4.txt"
#DOH_BLOCKLIST_NEW="/tmp/doh-ipv4-new.txt"
#DOH_BLOCKLIST_FALLBACK="/doh-ipv4.txt"
#
#echo "Downloading DoH blocklist from $DOH_BLOCKLIST_URL..."
#
# Attempt to download the DoH blocklist while handling errors safely
#{
#    curl -v --fail --connect-timeout 10 --max-time 30 --retry 3 --retry-delay 5 -o "$DOH_BLOCKLIST_NEW" "$DOH_BLOCKLIST_URL"
#} || {
#    echo "Download failed due to permission or network error."
#}
#
# Check if the downloaded file is valid (not empty), otherwise use fallback
#if [ ! -s "$DOH_BLOCKLIST_NEW" ]; then
#    echo "Download failed or file is empty, falling back to $DOH_BLOCKLIST_FALLBACK"
#
#    if [ -s "$DOH_BLOCKLIST_FALLBACK" ]; then
#        echo "Using fallback blocklist."
#        cp "$DOH_BLOCKLIST_FALLBACK" "$DOH_BLOCKLIST_NEW"
#    else
#        echo "Error: No valid blocklist file available. Exiting."
#        exit 1
#    fi
#else
#    echo "Download successful, using $DOH_BLOCKLIST_NEW"
#fi
#
# Process the blocklist and apply nftables rules
#echo "Applying nftables rules..."
#while read -r ip; do
#    if [[ -n "$ip" ]]; then
#        sudo nft add rule ip dns-redir prerouting iif \{ "${interfaces[*]}" \} ip daddr "$ip" tcp dport 443 counter drop || echo "Warning: Failed to add rule for $ip"
#    fi
#done < <(sed 's/\s.*//' "$DOH_BLOCKLIST_NEW")
#
#echo "DoH blocking rules applied successfully."

/usr/local/sbin/pdns_recursor-startup "$@"

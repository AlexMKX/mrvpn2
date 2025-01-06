#!/bin/bash
handle_interrupt(){
    wg-quick down "/tmp/$WG_INTERFACE.conf"
    exit 1
}
trap 'handle_interrupt' SIGTERM
set -e

# PMTU MSS FIX for wireguard
nft add table wireguard
nft add chain wireguard clamp_fix  "{ type filter hook forward priority 0 ; }"
nft flush chain wireguard clamp_fix
nft add rule wireguard clamp_fix meta iifkind wireguard counter  tcp flags syn tcp option maxseg size set rt mtu;

target="/tmp/$WG_INTERFACE.conf"
conf="/conf/interface/$WG_INTERFACE.conf"

#cat "/conf/interface/$WG_INTERFACE.conf" /conf/peers/* > "/tmp/$WG_INTERFACE.conf"

# Check if the peers directory is not empty
if [ "$(ls -A /conf/peers)" ]; then
  # If not empty, concatenate all files
  cat "$conf" /conf/peers/* > "${target}"
else
  # If empty, just copy the main configuration file
  cat "$conf" > "${target}"
fi

cat "/tmp/$WG_INTERFACE.conf"
chmod 0600 "/tmp/$WG_INTERFACE.conf"
wg-quick up "/tmp/$WG_INTERFACE.conf"
while true; do
    sleep 1
done

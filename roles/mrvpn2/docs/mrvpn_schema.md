```yaml
# tunnels declaration
tunnels:
  #tunnel name will be used as interface name
  wg_uk:
    # The tunnel p2p subnet, the ip addresses for the peers will be auto-assigned. 
    subnet: "10.9.20.0/24"
    #hosts participating in tunnel
    hosts:
      #host name (the same as in inventory)
      out-mrvpn-uk:
        # The port to be exposed. if not defined, this peer will not expose any port
        # It is renders as ip (or hostname) :port in the peer configuration. 
        # The ip or hostname is inferred from inventory ansible_host 
        expose: 55824
        # Will it auto start on boot (as a compose service). Should not be set for the peers with "compose_service" arg
        autostart: true
        # The wireguard table to be used for this peer
        table: "off"
        # The allowed networks for this peer (renders to the wireguard configuration)
        allowed_nets: [ 0.0.0.0/0 ]
        # will be traffic masqueraded
        masquerade: true
      mrvpn-entry:
        allowed_nets: [ 0.0.0.0/0]
        # The compose service, this peer will be injected.
        # In this case the wg_uk tunnel will be run in the firezone compose service namespace.
        compose_service: firezone
        masquerade: true
        table: "off"
  wg_tik:
    subnet: "10.9.22.0/24"
    hosts:
      mikrotik_router:
        allowed_nets: [ 0.0.0.0/0 ]
        table: "wg_tik"
        masquerade: true
        # The pre-cleanup and post-deploy hooks to be executed on mikrotik
        mikrotik_cleanup:
          - ':foreach i in=[/interface list member find comment="wg_tik"] do={ :do { /interface list member remove $i } on-error={} }'
        mikrotik_deploy:
          - '/interface list member add interface=wg_tik list=LAN comment="wg_tik"'
      mrvpn-entry:
        expose: 55825
        allowed_nets: [ 0.0.0.0/0 ]
        compose_service: firezone
        masquerade: true
        table: "off"

# The routing schema - how IPTServer will apply routing rules on entrypoint host.
routing:
  routes:
    # The routes that goes through default gateway
    # _DEFAULT is a special interface name that will be replaced with the default gateway interface name
    - interface: _DEFAULT
      # The metric for the routes
      metric: 100
      # Geo routing section. 
      geo:
        # The subnets with the country code to be routed through the interface
        - country='RU'
      # Domain routing section
      domains:
      # The domains, matched this regexp will be routed through the interface
        - .*\.ru
    - interface: wg_uk
      # Static routing. Everything that matches this CIDR will be routed through the wg_uk tunnel. 
      # It similar to the default gateway.
      static:
        - 0.0.0.0/0

  # The mark (packet mark) to be used for PBR
  pbr_mark: 200
  # The table to be used for PBR
  table: 200
  # The ingress interfaces in the entrypoint host participating in the routing. 
  interfaces:
    - wg-firezone
    - wg_tik

# The services in which namespaces the routing will be applied
services:
  firezone:
    - wg-firezone
    - wg_tik

# The inventory hostname for the entrypoint.
entrypoint: mrvpn-entry

# The firezone configuration according to the firezone schema (see below)
firezone:
  fz_client_subnet: 10.0.23.0/24
  fz_server_url: https://mrvpn-entry.domain.tld
  fz_admin_password: "PASSWORD"
  fz_ospf:
  fz_oidc:
    google:
      client_id: "GOOGLE OIDC CLIENT ID"
      client_secret: "GOOGLE OIDC CLIENT SECRET"

mrvpn_root: /opt/mrvpn
```

# References
[Firezone Readme](../../firezone/README.md) 
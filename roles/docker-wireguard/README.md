```ansible

- hosts:  host1, host2
  tasks:
    - set_fact:
        tunnel: "tunnel_name"
    - include_role:
        name: ../roles/docker-wireguard
      vars:
        wg_tunnel_name: "{{tunnel}}"
        wg_interface: "{{tunnels[tunnel].hosts[inventory_hostname]}}"
    - debug:
        msg: "{{tunnels[tunnel].interface}}"
- hosts: outer, vpn-dev.xxl.cx
  name: Apply Peers
  tasks:
    - set_fact:
        tunnel: "tunnel_name"
    - set_fact:
        other_hosts: "{{tunnels[tunnel].hosts.keys() | difference([inventory_hostname])}}"
    - debug:
        msg: "{{tunnels[tunnel]}}"
    - set_fact:
        peers: "{{ peers| default({}) | combine({item: hostvars[item].tunnels[tunnel].interface}) }}"
      with_items: "{{other_hosts}}"
    - include_role:
        name: ../roles/docker-wireguard
      vars:
        wg_peers: "{{peers}}"
        wg_tunnel_name: "{{tunnel}}"

```

```yaml
  children:
    tunnel_name:
      hosts:
        outer:
        vpn-dev.xxl.cx:
      vars:
        tunnels:
          tunnel_name:
            subnet: "10.8.1.0/24"
            hosts:
              host1:
                port: 55820
                ip_num: 1
              host2:
                ip_num: 2
                # each who has this peer will route traffic to these networks through this peer
                routes: 192.168.88.0/24
                # use if you want the container use specific's service network namespace
                #compose_service: firezone
                # use if you need the container run in compose network
                compose_network: "firezone-network"
                # if you need masquerade traffic to the peer
                masquerade: true
```

# todo
- add masquerdate handling  
- add routes handling  
- add compose service start (when no compose network or compose service is provided). think about mark it as
standalone (which means not in compose)  
- add config recreation flag  
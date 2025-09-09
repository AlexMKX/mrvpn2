Role Name
=========

The role to fully install MRVPN2 on the infrastructure.

Requirements
------------

None. In case of any error to occur, it runs prepare_hosts.yml tasks to install the required packages where 
they are needed.

Role Variables
--------------

The role expects the mrvpn_config variable to contain the VPN schema. 
```yaml
    - name: Execute mrvpn2 role
      include_role:
        name: alexmkx.mrvpn2.mrvpn2

      vars:
        mrvpn_config: "{{mrvpn_config_file.ansible_facts}}"
```
The details on schema can be found in the [mrvpn_schema.md](./docs/mrvpn_schema.md) file.

Dependencies
------------
linux packages (setup automatically on failure):
```
- rsync
- wireguard
- python3-pip
- wireguard-tools
- python3-paramiko
- python3-jmespath
- curl
- jq
- python-is-python3
- python3-netaddr
```
Roles:
```
- geerlingguy.docker
```
Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - name: Execute mrvpn2 role
      include_role:
        name: alexmkx.mrvpn2.mrvpn2

      vars:
        mrvpn_config: "{{mrvpn_config_file.ansible_facts}}"

License
-------

BSD

.

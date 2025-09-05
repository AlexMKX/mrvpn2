"""
Docker Compose Patching Module
This module patches Docker Compose files by merging service configurations,
handling network mode dependencies, and managing port mappings between services.
"""

from ansible.module_utils.basic import AnsibleModule


def main():
    from collections import defaultdict
    import yaml, base64
    try:
        args = dict(
            compose_contents=dict(type='list',
                                  required=True),
        )
        ansible = AnsibleModule(
            argument_spec=args,
            supports_check_mode=True)

        compose_files = ansible.params['compose_contents']
        decoded = {i['source']: yaml.safe_load(base64.b64decode(i['content'])) for i in compose_files}
        target_services = defaultdict(list)

        for yi, yc in decoded.items():
            if 'services' in yc:
                for si, sc in yc['services'].items():
                    if sc.get('network_mode', '').split(':')[0].lower() == 'service':
                        ts = sc.get('network_mode', '').split(':')[1]
                        if 'ports' in sc:
                            target_services[ts].extend(sc.pop('ports'))

        for yi, yc in decoded.items():
            if 'services' in yc:
                for si, sc in yc['services'].items():
                    if si in target_services.keys():
                        sc['ports'] = list(set(sc.get('ports', []) + target_services[si]))

        ansible_result = dict(
            status=200,
            changed=True,
            result=decoded)
    except Exception as e:
        ansible_result = ansible.fail_json(msg=str(e),
                                           status=400,
                                           result={})

    ansible.exit_json(**ansible_result)


if __name__ == '__main__':
    main()

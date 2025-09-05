#!/usr/bin/python
"""
Firezone OIDC Configuration Generator Module
This module generates OIDC (OpenID Connect) configuration for Firezone authentication,
processing OIDC provider settings and creating base64 encoded configuration for
integration with external identity providers.
"""

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'GFN-CIS'
}

DOCUMENTATION = """
---
module: fz_gen_oidc
short_description: Generate OIDC configuration for Firezone
description:
  - This module generates OIDC configuration for Firezone authentication
  - It processes OIDC provider settings and creates base64 encoded configuration
version_added: "1.0"
author: "GFN-CIS"
options:
  oidc:
    description:
      - Dictionary containing OIDC provider configurations
    required: true
    type: dict
"""

EXAMPLES = """
---
- name: Generate OIDC configuration
  fz_gen_oidc:
    oidc:
      google:
        client_id: "your_client_id"
        client_secret: "your_client_secret"
        discovery_document_uri: "https://accounts.google.com/.well-known/openid-configuration"
        scope: "openid email profile"
"""

RETURN = """
---
result:
  description: Generated OIDC configuration
  type: dict
  returned: success
  contains:
    config:
      description: Base64 encoded OIDC configuration
      type: str
    redirects:
      description: List of redirect URIs
      type: list
      elements: str
"""

import subprocess
import logging
import json
import string
import base64
from ansible.module_utils.basic import AnsibleModule


def main():
    ansible = AnsibleModule(
        argument_spec=dict(oidc=dict(type='dict',
                                     required=True), ),
        supports_check_mode=True)
    r = list()
    redirects = list()
    for key, value in ansible.params['oidc'].items():
        p = {"id": key.translate({ord(c): None for c in string.whitespace}).lower(),
             "client_id": value['client_id'], "client_secret": value['client_secret'],
             'discovery_document_uri': value.get(
                 'discovery_document_uri', 'https://accounts.google.com/.well-known/openid-configuration'),
             'redirect_uri': value.get('redirect_uri', None),
             'scope': value.get('scope', 'openid email profile'),
             'auto_create_users': value.get('auto_create_users', True),
             'label': value.get('label', key),
             'response_type': value.get('response_type', 'code'),
             }
        r.append(p)
        redirects.append("/auth/oidc/" + p['id'] + "/callback/")

    ansible_result = dict(
        changed=True,
        result={"config": base64.b64encode(json.dumps(r).encode('utf-8')), "redirects": redirects}
    )

    ansible.exit_json(**ansible_result)


if __name__ == '__main__':
    main()

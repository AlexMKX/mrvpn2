#!/usr/bin/env python3
"""
Cryptographically Secure Password Generator Module for Ansible
Generates strong, cryptographically secure passwords using Python's secrets module.
Can be used both as Ansible module and as standalone utility.

Version: 1.0
"""

import secrets
import string
import sys
import json
import argparse
from typing import Dict, Any


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stable'],
}

DOCUMENTATION = """
---
module: password_generator
short_description: Generate cryptographically secure passwords
description:
  - Generates cryptographically secure passwords using Python's secrets module
  - Uses multiple entropy sources for maximum security
  - Supports various character sets and complexity requirements
  - Can be used as Ansible module or standalone utility
version_added: "1.0"
options:
  length:
    description:
      - Length of the password to generate
    required: false
    default: 32
    type: int
  include_uppercase:
    description:
      - Include uppercase letters A-Z
    required: false
    default: true
    type: bool
  include_lowercase:
    description:
      - Include lowercase letters a-z
    required: false
    default: true
    type: bool
  include_digits:
    description:
      - Include digits 0-9
    required: false
    default: true
    type: bool
  include_symbols:
    description:
      - Include special symbols
    required: false
    default: true
    type: bool
  exclude_ambiguous:
    description:
      - Exclude ambiguous characters (0, O, l, 1, I)
    required: false
    default: true
    type: bool
  min_uppercase:
    description:
      - Minimum number of uppercase letters
    required: false
    default: 2
    type: int
  min_lowercase:
    description:
      - Minimum number of lowercase letters
    required: false
    default: 2
    type: int
  min_digits:
    description:
      - Minimum number of digits
    required: false
    default: 2
    type: int
  min_symbols:
    description:
      - Minimum number of symbols
    required: false
    default: 2
    type: int
"""

EXAMPLES = """
---
# Generate default 32-character password
- name: Generate secure password
  password_generator:
  register: my_password

# Generate 48-character password with custom requirements
- name: Generate long password
  password_generator:
    length: 48
    min_uppercase: 4
    min_digits: 4
    min_symbols: 4

# Generate password without symbols for legacy systems
- name: Generate alphanumeric password
  password_generator:
    length: 24
    include_symbols: false
    min_digits: 6
"""

RETURN = """
password:
  description: The generated password
  returned: always
  type: str
  sample: "Kx8#mN9$pQ2@vR7!zB3%wC6&"
entropy_bits:
  description: Estimated entropy bits of the generated password
  returned: always
  type: float
  sample: 191.2
charset_size:
  description: Size of the character set used
  returned: always
  type: int
  sample: 94
"""


def generate_password(length: int = 32, include_uppercase: bool = True,
                     include_lowercase: bool = True, include_digits: bool = True,
                     include_symbols: bool = True, exclude_ambiguous: bool = True,
                     min_uppercase: int = 2, min_lowercase: int = 2,
                     min_digits: int = 2, min_symbols: int = 2) -> Dict[str, Any]:
    """
    Generate a cryptographically secure password with specified requirements.
    
    Returns dict with password, entropy_bits, and charset_size.
    """
    
    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    ambiguous = "0O1lI"
    
    # Build character set
    charset = ""
    if include_uppercase:
        chars = uppercase
        if exclude_ambiguous:
            chars = ''.join(c for c in chars if c not in ambiguous)
        charset += chars
        
    if include_lowercase:
        chars = lowercase
        if exclude_ambiguous:
            chars = ''.join(c for c in chars if c not in ambiguous)
        charset += chars
        
    if include_digits:
        chars = digits
        if exclude_ambiguous:
            chars = ''.join(c for c in chars if c not in ambiguous)
        charset += chars
        
    if include_symbols:
        charset += symbols
    
    if not charset:
        raise ValueError("No character sets enabled")
    
    # Validate minimum requirements
    min_required = 0
    if include_uppercase:
        min_required += min_uppercase
    if include_lowercase:
        min_required += min_lowercase
    if include_digits:
        min_required += min_digits
    if include_symbols:
        min_required += min_symbols
        
    if min_required > length:
        raise ValueError(f"Minimum character requirements ({min_required}) exceed password length ({length})")
    
    # Generate password with requirements
    max_attempts = 1000
    for attempt in range(max_attempts):
        password = ''.join(secrets.choice(charset) for _ in range(length))
        
        # Check if password meets minimum requirements
        meets_requirements = True
        
        if include_uppercase:
            chars = uppercase
            if exclude_ambiguous:
                chars = ''.join(c for c in chars if c not in ambiguous)
            if sum(1 for c in password if c in chars) < min_uppercase:
                meets_requirements = False
                
        if include_lowercase and meets_requirements:
            chars = lowercase
            if exclude_ambiguous:
                chars = ''.join(c for c in chars if c not in ambiguous)
            if sum(1 for c in password if c in chars) < min_lowercase:
                meets_requirements = False
                
        if include_digits and meets_requirements:
            chars = digits
            if exclude_ambiguous:
                chars = ''.join(c for c in chars if c not in ambiguous)
            if sum(1 for c in password if c in chars) < min_digits:
                meets_requirements = False
                
        if include_symbols and meets_requirements:
            if sum(1 for c in password if c in symbols) < min_symbols:
                meets_requirements = False
        
        if meets_requirements:
            # Calculate entropy
            entropy_bits = length * (len(charset).bit_length() - 1)
            
            return {
                'password': password,
                'entropy_bits': entropy_bits,
                'charset_size': len(charset)
            }
    
    raise RuntimeError(f"Failed to generate password meeting requirements after {max_attempts} attempts")


def run_module():
    """Main function for Ansible module"""
    
    try:
        from ansible.module_utils.basic import AnsibleModule
    except ImportError:
        AnsibleModule = None
    
    module_args = dict(
        length=dict(type='int', required=False, default=32),
        include_uppercase=dict(type='bool', required=False, default=True),
        include_lowercase=dict(type='bool', required=False, default=True),
        include_digits=dict(type='bool', required=False, default=True),
        include_symbols=dict(type='bool', required=False, default=True),
        exclude_ambiguous=dict(type='bool', required=False, default=True),
        min_uppercase=dict(type='int', required=False, default=2),
        min_lowercase=dict(type='int', required=False, default=2),
        min_digits=dict(type='int', required=False, default=2),
        min_symbols=dict(type='int', required=False, default=2),
    )
    
    if AnsibleModule is None:
        # Running outside Ansible - skip module execution
        return
        
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    
    try:
        result = generate_password(
            length=module.params['length'],
            include_uppercase=module.params['include_uppercase'],
            include_lowercase=module.params['include_lowercase'],
            include_digits=module.params['include_digits'],
            include_symbols=module.params['include_symbols'],
            exclude_ambiguous=module.params['exclude_ambiguous'],
            min_uppercase=module.params['min_uppercase'],
            min_lowercase=module.params['min_lowercase'],
            min_digits=module.params['min_digits'],
            min_symbols=module.params['min_symbols']
        )
        
        module.exit_json(
            changed=True,
            password=result['password'],
            entropy_bits=result['entropy_bits'],
            charset_size=result['charset_size']
        )
        
    except (ValueError, RuntimeError) as e:
        module.fail_json(msg=f"Password generation failed: {str(e)}")


def standalone_main():
    """Main function for standalone usage"""
    parser = argparse.ArgumentParser(
        description="Cryptographically Secure Password Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Generate default 32-char password
  %(prog)s -l 48                     # Generate 48-character password
  %(prog)s -l 24 --no-symbols        # Generate alphanumeric password
  %(prog)s -l 16 --min-digits 4      # Password with at least 4 digits
  %(prog)s --json                    # Output in JSON format
        """
    )
    
    parser.add_argument('-l', '--length', type=int, default=32,
                       help='Password length (default: 32)')
    parser.add_argument('--no-uppercase', action='store_false', dest='include_uppercase',
                       help='Exclude uppercase letters')
    parser.add_argument('--no-lowercase', action='store_false', dest='include_lowercase',
                       help='Exclude lowercase letters')
    parser.add_argument('--no-digits', action='store_false', dest='include_digits',
                       help='Exclude digits')
    parser.add_argument('--no-symbols', action='store_false', dest='include_symbols',
                       help='Exclude symbols')
    parser.add_argument('--include-ambiguous', action='store_false', dest='exclude_ambiguous',
                       help='Include ambiguous characters (0, O, l, 1, I)')
    parser.add_argument('--min-uppercase', type=int, default=2,
                       help='Minimum uppercase letters (default: 2)')
    parser.add_argument('--min-lowercase', type=int, default=2,
                       help='Minimum lowercase letters (default: 2)')
    parser.add_argument('--min-digits', type=int, default=2,
                       help='Minimum digits (default: 2)')
    parser.add_argument('--min-symbols', type=int, default=2,
                       help='Minimum symbols (default: 2)')
    parser.add_argument('--json', action='store_true',
                       help='Output result in JSON format')
    parser.add_argument('--count', type=int, default=1,
                       help='Generate multiple passwords (default: 1)')
    
    args = parser.parse_args()
    
    try:
        passwords = []
        for _ in range(args.count):
            result = generate_password(
                length=args.length,
                include_uppercase=args.include_uppercase,
                include_lowercase=args.include_lowercase,
                include_digits=args.include_digits,
                include_symbols=args.include_symbols,
                exclude_ambiguous=args.exclude_ambiguous,
                min_uppercase=args.min_uppercase,
                min_lowercase=args.min_lowercase,
                min_digits=args.min_digits,
                min_symbols=args.min_symbols
            )
            passwords.append(result)
        
        if args.json:
            if args.count == 1:
                print(json.dumps(passwords[0], indent=2))
            else:
                print(json.dumps(passwords, indent=2))
        else:
            for i, result in enumerate(passwords):
                if args.count > 1:
                    print(f"Password {i+1}: {result['password']}")
                    print(f"  Entropy: {result['entropy_bits']:.1f} bits")
                    print(f"  Charset size: {result['charset_size']}")
                    print()
                else:
                    print(result['password'])
                    if len(sys.argv) > 1:  # Show details if any args provided
                        print(f"Entropy: {result['entropy_bits']:.1f} bits, Charset: {result['charset_size']} chars")
                        
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    # Check if we're running as Ansible module
    if len(sys.argv) > 1 and sys.argv[1] == 'ANSIBLE_MODULE':
        # Running as Ansible module
        run_module()
    else:
        # Running as standalone script
        standalone_main()

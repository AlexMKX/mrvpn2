#!/usr/bin/env python3
"""
Password Generation Filter Plugin for Ansible
Provides password_generator filter for use in Jinja2 templates.

Usage in templates:
  {{ SOME_VAR | default(password_generator(24)) }}
  {{ '' | password_generator(48, include_symbols=false) }}
"""

import secrets
import string


def password_generator(value, length=32, include_uppercase=True, include_lowercase=True,
                      include_digits=True, include_symbols=True, exclude_ambiguous=True,
                      min_uppercase=2, min_lowercase=2, min_digits=2, min_symbols=2):
    """
    Generate cryptographically secure password.
    
    Args:
        value: Input value (ignored, can be empty string)
        length: Password length
        include_uppercase: Include uppercase letters
        include_lowercase: Include lowercase letters  
        include_digits: Include digits
        include_symbols: Include symbols
        exclude_ambiguous: Exclude ambiguous characters
        min_uppercase: Minimum uppercase letters
        min_lowercase: Minimum lowercase letters
        min_digits: Minimum digits
        min_symbols: Minimum symbols
        
    Returns:
        Generated password string
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
            return password
    
    raise RuntimeError(f"Failed to generate password meeting requirements after {max_attempts} attempts")


class FilterModule(object):
    """Ansible filter plugin"""
    
    def filters(self):
        return {
            'password_generator': password_generator,
            'generate_password': password_generator,  # Alias
        }

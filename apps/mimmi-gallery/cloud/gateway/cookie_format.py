"""Accept either a raw owner ndus value or an existing Cookie header.

rclone-extra passes this option directly to HTTP's Cookie header. Formatting
must happen in its existing child-process environment, never in URLs or logs.
"""
import re


def cookie_header(value):
    if not isinstance(value,str) or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Invalid owner storage cookie configuration')
    value=value.strip()
    if value.lower().startswith('cookie:'):
        value=value.split(':',1)[1].strip()
    if not value:return ''
    if re.search(r'(?:^|;\s*)ndus=',value):return value
    if len(value)>=8 and re.fullmatch(r'[A-Za-z0-9_%+./~-]+={0,2}',value):
        return 'ndus='+value
    # Preserve a complete existing header rather than dropping other cookies.
    return value

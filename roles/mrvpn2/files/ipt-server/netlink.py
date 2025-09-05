import socket
import struct
import os
import fcntl
from array import array

# Netlink constants
RTM_NEWROUTE = 24
RTM_DELROUTE = 25
NLM_F_REQUEST = 1
NLM_F_ACK = 4
NLM_F_CREATE = 1024
NLM_F_EXCL = 512
NLMSG_ERROR = 2

# Scopes
RT_SCOPE_LINK = 2       # Directly connected route
RT_SCOPE_UNIVERSE = 0   # Global route via gateway

# Route message attributes (Linux definitions)
RTA_DST = 1
RTA_OIF = 4
RTA_GATEWAY = 5
RTA_PRIORITY = 6

def inet_aton(ip_str):
    return socket.inet_aton(ip_str)

def check_interface(ifindex):
    """Return the interface name if it exists, otherwise None."""
    try:
        ifname = socket.if_indextoname(ifindex)
        print(f"Interface {ifindex} exists: {ifname}")
        return ifname
    except Exception as e:
        print(f"Interface {ifindex} check failed: {e}")
        return None

def pack_netlink_msg(nlmsg_type, flags, seq, route_dict):
    """Pack a single netlink message for a route operation."""
    attrs = []
    if 'dst' in route_dict:
        attrs.append((RTA_DST, inet_aton(route_dict['dst'])))
    if 'gateway' in route_dict:
        attrs.append((RTA_GATEWAY, inet_aton(route_dict['gateway'])))
    if 'oif' in route_dict:
        attrs.append((RTA_OIF, struct.pack('I', route_dict['oif'])))
    if 'priority' in route_dict:
        attrs.append((RTA_PRIORITY, struct.pack('I', route_dict['priority'])))

    # Base header length: netlink header (16 bytes) + route message header (12 bytes)
    nlmsg_len = 16 + 12
    for attr_type, attr_data in attrs:
        nlmsg_len += 4 + ((len(attr_data) + 3) & ~3)

    msg = array('B')
    msg.extend(struct.pack('IHHII', nlmsg_len, nlmsg_type, flags, seq, os.getpid()))

    family = route_dict.get('family', socket.AF_INET)
    dst_len = route_dict.get('dst_len', 32)
    table = route_dict.get('table', 254)
    proto = route_dict.get('proto', 4)  # default RTPROT_BOOT
    rtype = route_dict.get('type', 1)
    # If a gateway is provided, use global scope; otherwise assume link scope.
    scope = route_dict.get('scope', (RT_SCOPE_UNIVERSE if 'gateway' in route_dict else RT_SCOPE_LINK))

    # Route message payload: family, dst_len, src_len, tos, table, proto, scope, type, flags
    msg.extend(struct.pack('BBBBBBBBI',
                           family, dst_len, 0, 0, table, proto, scope, rtype, 0))

    for attr_type, attr_data in attrs:
        attr_len = len(attr_data) + 4  # each attribute header is 4 bytes
        msg.extend(struct.pack('HH', attr_len, attr_type))
        msg.extend(attr_data)
        padding = (4 - (len(attr_data) % 4)) % 4
        msg.extend(b'\0' * padding)

    return msg

def parse_netlink_responses(data):
    """Parse a buffer of netlink responses, returning a dict mapping sequence number to (success, message)."""
    responses = {}
    pos = 0
    while pos < len(data):
        if pos + 16 > len(data):
            break
        nlmsg_len, nlmsg_type, nlmsg_flags, nlmsg_seq, nlmsg_pid = struct.unpack_from('IHHII', data, pos)
        if nlmsg_len < 16 or pos + nlmsg_len > len(data):
            break
        if nlmsg_type == NLMSG_ERROR:
            error_code = struct.unpack_from('i', data, pos + 16)[0]
            if error_code == 0:
                responses[nlmsg_seq] = (True, "Operation succeeded")
            else:
                error_msg = os.strerror(-error_code) if error_code < 0 else f"Unknown error {error_code}"
                responses[nlmsg_seq] = (False, f"Operation failed: {error_msg}")
        else:
            responses[nlmsg_seq] = (True, "Operation succeeded (non-error response)")
        pos += (nlmsg_len + 3) & ~3
    return responses

def add_routes(routes):
    """Add a list of routes in one batch."""
    nl_sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE)
    nl_sock.bind((0, 0))
    nl_sock.settimeout(2)
    msgs = bytearray()
    seq_to_route = {}
    seq = 1
    for route in routes:
        # if not check_interface(route.get('oif', 0)):
        #     print(f"Interface {route.get('oif')} does not exist. Skipping route: {route}")
        #     continue
        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = pack_netlink_msg(RTM_NEWROUTE, flags, seq, route)
        msgs.extend(msg.tobytes())
        seq_to_route[seq] = route
        seq += 1

    nl_sock.send(msgs)
    responses = {}
    expected_seqs = set(seq_to_route.keys())
    try:
        while expected_seqs:
            data = nl_sock.recv(4096)
            new_responses = parse_netlink_responses(data)
            for s, res in new_responses.items():
                if s in expected_seqs:
                    responses[s] = res
                    expected_seqs.remove(s)
    except socket.timeout:
        print("Timeout waiting for responses")
    for s, route in seq_to_route.items():
        success, message = responses.get(s, (False, "No response"))
        route_str = f"{route.get('dst','')}/{route.get('dst_len','')} " \
                    f"gateway: {route.get('gateway','')} " \
                    f"oif: {route.get('oif','')} " \
                    f"priority: {route.get('priority','')} " \
                    f"table: {route.get('table','')}"
        if not success:
            print(f"Failed to add route {route_str}: {message}")
    nl_sock.close()

def delete_routes(routes):
    """Delete a list of routes in one batch."""
    nl_sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE)
    nl_sock.bind((0, 0))
    nl_sock.settimeout(2)
    msgs = bytearray()
    seq_to_route = {}
    seq = 1
    for route in routes:
        flags = NLM_F_REQUEST | NLM_F_ACK
        msg = pack_netlink_msg(RTM_DELROUTE, flags, seq, route)
        msgs.extend(msg.tobytes())
        seq_to_route[seq] = route
        seq += 1

    nl_sock.send(msgs)
    responses = {}
    expected_seqs = set(seq_to_route.keys())
    try:
        while expected_seqs:
            data = nl_sock.recv(4096)
            new_responses = parse_netlink_responses(data)
            for s, res in new_responses.items():
                if s in expected_seqs:
                    responses[s] = res
                    expected_seqs.remove(s)
    except socket.timeout:
        print("Timeout waiting for responses")
    for s, route in seq_to_route.items():
        success, message = responses.get(s, (False, "No response"))
        route_str = f"{route.get('dst','')}/{route.get('dst_len','')} " \
                    f"gateway: {route.get('gateway','')} " \
                    f"oif: {route.get('oif','')} " \
                    f"priority: {route.get('priority','')} " \
                    f"table: {route.get('table','')}"
        if success:
            print(f"Successfully deleted route: {route_str}")
        else:
            print(f"Failed to delete route {route_str}: {message}")
    nl_sock.close()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root")
        exit(1)

    # Example list of routes to add/delete.
    # Adjust the values as needed for your network.
    routes = [
        {
            'dst': '2.16.20.0',
            'dst_len': 23,
            'family': socket.AF_INET,
            'oif': 2,
            'priority': 100,
            'proto': 3,
            'table': 200,
            'type': 1,
            'gateway': '2.16.20.1'
        },
        {
            'dst': '3.16.20.0',
            'dst_len': 24,
            'family': socket.AF_INET,
            'oif': 2,
            'priority': 110,
            'proto': 3,
            'table': 200,
            'type': 1,
            'gateway': '3.16.20.1'
        }
    ]

    print("Adding routes...")
    add_routes(routes)

    print("Deleting routes...")
    delete_routes(routes)

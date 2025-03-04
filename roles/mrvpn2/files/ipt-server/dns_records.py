import ipaddress


class ARecord:
    name: str
    query: str
    content: str

    def __init__(self, request: dict):
        if request['type'] != 1:
            raise ValueError("Invalid record type")
        self.name = request['name'].rstrip('.')
        self.query = request['query'].rstrip('.')
        self.content = request['content']

    @property
    def ip(self) -> ipaddress.IPv4Network:
        return ipaddress.IPv4Network(self.content)

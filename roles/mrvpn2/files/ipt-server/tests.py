import unittest
from unittest.mock import patch, PropertyMock, MagicMock
from Router import Router
from Config import CountryRoute, DomainRoute, NetRoute, MySettings
import ipaddress
import logging, os
from dns_records import ARecord

logging_level = os.environ.get('LOGLEVEL', 'DEBUG').upper()
logging.basicConfig(
    level=getattr(logging, logging_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class TestRouter(unittest.TestCase):

    def setUp(self):
        self.mock_interfaces = {
            'eth0': [(1, 0)],
            'eth1': [(2, 0)],
            'eth2': [(3, 0)],
            'eth3': [(4, 0)],
            '_DEFAULT': [(1, None)]
        }
        self.country_routes = {
            'US': [ipaddress.IPv4Network('192.0.2.0/24'), ipaddress.IPv4Network('198.51.100.0/24')],
            'UK': [ipaddress.IPv4Network('203.0.113.0/24'), ipaddress.IPv4Network('202.0.113.0/24')]
        }

    @patch('Router.Router._process_route_commands_iproute2')
    @patch('route.RouteObject.interfaces', new_callable=PropertyMock)
    @patch('ip_database.IPDB')
    def test_on_a_record(self, mock_IPDB, mock_interfaces, mock_process_route_commands_iproute2):
        # Set up mock interfaces
        mock_interfaces.return_value = self.mock_interfaces

        # Mock the IPDB object to return some test subnets
        mock_IPDB.__getitem__.side_effect = lambda country: self.country_routes.get(country, [])

        # Create a real MySettings object with country, domain, and net routes
        dom_r = DomainRoute(
            type="domain",
            domain=r".*\.example\.com",
            metric=300,
            weight=50,
            interface="eth2",
        )
        dom_r2 = DomainRoute(
            type="domain",
            domain=r"test\.example\.com",
            metric=300,
            weight=50,
            interface="_DEFAULT",
        )
        config = MySettings(
            table=100,
            routes=[
                CountryRoute(
                    type="country",
                    country="US",
                    metric=100,
                    weight=10,
                    interface="eth0",
                ),
                CountryRoute(
                    type="country",
                    country="UK",
                    metric=200,
                    weight=20,
                    interface="eth1",
                ),
                dom_r, dom_r2,
                NetRoute(
                    type="net",
                    net="10.0.0.0/8",
                    metric=400,
                    weight=2,
                    interface="_DEFAULT",
                )
            ],
            ws_port=8080,
            db='test_db',
            pbr_mark=1,
            interfaces=['eth0', 'eth1', 'eth2', 'eth3']
        )

        # Create Router instance with mocked country lookup
        router = Router(config)

        # Test with a IP - net US, domain priority before the subnet priority
        # Expeted result: network is added
        a_record_us = ARecord({
            'query': 'us.example.com.',
            'content': '192.0.2.1',
            'name': 'us.example.com.',
            'type': 1
        })

        router.on_a_record(a_record_us)

        added_routes_us = [interval for interval in router._route_tree if
                           interval.begin == interval.end - 1 == int(ipaddress.IPv4Address('192.0.2.1'))]

        self.assertEqual(len(added_routes_us), 1, "Should have added exactly one route for us.example.com IP")
        added_route_us = added_routes_us[0].data

        self.assertEqual(str(added_route_us.net), '192.0.2.1/32')
        self.assertEqual(added_route_us.interface, dom_r.interface, "US IP should be routed through US interface")
        self.assertEqual(added_route_us.metric, dom_r.metric)
        self.assertEqual(added_route_us.weight, dom_r.weight)

        # Test with a UK IP
        a_record_uk = ARecord({
            'query': 'uk.example.com.',
            'content': '10.0.0.1',
            'name': 'uk.example.com.',
            'type': 1
        })

        router.on_a_record(a_record_uk)

        added_routes_uk = [interval for interval in router._route_tree if
                           interval.begin == interval.end - 1 == int(ipaddress.IPv4Address('10.0.0.1'))]

        self.assertEqual(len(added_routes_uk), 0,
                         "Should not add route because it's weight after the 10.0.0.0/24 subnet")

        # Test with a domain-matched IP
        a_record_domain = ARecord({
            'query': 'test.example.com.',
            'content': '172.16.0.1',
            'name': 'test.example.com.',
            'type': 1
        })

        router.on_a_record(a_record_domain)

        added_routes_domain = [interval for interval in router._route_tree if
                               interval.begin == interval.end - 1 == int(ipaddress.IPv4Address('172.16.0.1'))]

        self.assertEqual(len(added_routes_domain), 1, "Should have added exactly one route for domain-matched IP")
        added_route_domain = added_routes_domain[0].data

        self.assertEqual(str(added_route_domain.net), '172.16.0.1/32')
        self.assertEqual(added_route_domain.interface, 'eth2',
                         "Domain-matched IP should be routed through domain interface")
        self.assertEqual(added_route_domain.metric, 300)
        self.assertEqual(added_route_domain.weight, 5)


if __name__ == '__main__':
    unittest.main()

from typing import Optional
from pyroute2 import IPBatch, IPRoute, Conntrack
from intervaltree import IntervalTree, Interval
from dns_records import ARecord

import queue
import Config
from route import RouteObject
import threading
import copy
from lib import *

import ipaddress

logger = logging.getLogger(__name__)


class Router:

    def _cleanup_expired_routes(self):
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(timeout=self._cleanup_interval)
            if self._shutdown_event.is_set():
                break
            with self._routes_lock:
                expired_intervals = [
                    interval for interval in self._route_tree
                    if interval.data.expired
                ]

                if not expired_intervals:
                    continue

                # Track which expired intervals have active connections
                intervals_to_keep = set()

                try:
                    for entry in self._conntrack.dump_entries():
                        try:
                            src_addr = int(ipaddress.ip_address(entry.tuple_orig.saddr))
                            dst_addr = int(ipaddress.ip_address(entry.tuple_orig.daddr))

                            # Check each expired interval to see if it contains this connection
                            for interval in expired_intervals:
                                if (interval.begin <= src_addr < interval.end or
                                        interval.begin <= dst_addr < interval.end):
                                    intervals_to_keep.add(interval)
                                    # Once we know we're keeping this interval, no need to check it again
                                    break
                        except Exception as e:
                            logger.debug(f"Error processing conntrack entry: {e}")
                except Exception as e:
                    logger.warning(f"Error accessing conntrack entries: {e}")

                # Process each expired interval
                for interval in expired_intervals:
                    if interval not in intervals_to_keep:
                        # No active connections, remove the route
                        self._route_tree.remove(interval)
                        route_spec = interval.data.route_spec
                        self._route_queue.put(("del", route_spec))
                        logger.info(f"Removed expired route: {interval.data.net}")

    def remove_conntrack_entries_for_destination(self, destination: IntervalTree):
        """
        Remove conntrack entries for a given destination IP or subnet using ct.dump_entries().
    
        Args:
            destination (str): Destination IP or subnet (e.g., "192.168.1.0/24" or "8.8.8.8")
        """
        #        return

        if not self._cfg.clean_conntrack:
            return
        try:
            deleted_count = 0
            for entry in self._conntrack.dump_entries():
                try:
                    src_addr = int(ipaddress.ip_address(entry.tuple_orig.saddr))
                    dst_addr = int(ipaddress.ip_address(entry.tuple_orig.daddr))

                    # Check if either source or destination IP is in any interval in the tree
                    if destination[src_addr] or destination[dst_addr]:
                        # Delete the entry
                        logger.debug(f'Delete conntrack entry {entry.tuple_orig}')
                        self._conntrack.entry('del', tuple_orig=entry.tuple_orig)
                        deleted_count += 1
                        logger.info(
                            f"Deleted conntrack entry: src={entry.tuple_orig.saddr}, dst={entry.tuple_orig.daddr}"
                        )
                except Exception as e:
                    logger.warning(f"Error processing conntrack entry: {entry.tuple_orig} {e}")
            else:
                logger.info(f"Deleted {deleted_count} conntrack entries.")

        except Exception as e:
            logger.warning(f"Error processing conntrack entries: {e}")
            raise

    def add_route(self, route: Config.RouteObject, immediate=False) -> Optional[RouteObject]:
        with self._routes_lock:
            net_start = route.net_start
            net_end = route.net_end

            # 1. Search for exact occurrence of the route and update if found
            existing_intervals = self._route_tree[net_start:net_end + 1]
            for interval in existing_intervals:
                if (interval.begin == net_start and interval.end == net_end + 1 and
                        interval.data.metric == route.metric and
                        interval.data.weight == route.weight and
                        interval.data.interface == route.interface):
                    # Update existing route
                    interval.data.reset_expiration(route.ttl)
                    return copy.deepcopy(interval.data)

            # 2. Check for overlaps with existing less-specific routes with higher weight
            overlapping_intervals = self._route_tree[net_start:net_end + 1]
            for interval in overlapping_intervals:
                if (interval.begin <= net_start and net_end < interval.end and
                        interval.end - interval.begin > net_end - net_start + 1 and
                        interval.data.weight > route.weight):
                    logging.info(
                        f"Skipping route for {route.net} due to overlapping route with less specific prefix and higher weight")
                    return copy.deepcopy(interval.data)

            # 3. If no exact match or overlapping route found, add the new route
            route.reset_expiration(route.ttl)
            new_interval = Interval(net_start, net_end + 1, route)
            self._route_tree.add(new_interval)
            logging.debug(f"Adding new route: {route}")
            if immediate:
                # Add the route immediately to the iproute2 kernel
                with IPRoute() as ipr:
                    try:
                        spec = route.route_spec.copy()
                        spec.update({'table': self._cfg.table})
                        rv = ipr.route("add", **spec)
                        logging.debug(f"Added route immediately: {route} spec:{spec} {rv}")
                    except Exception as e:
                        logging.warning(f"Error adding route immediately: {route} {e}")
            else:
                self._route_queue.put(("add", route.route_spec))
            return copy.deepcopy(new_interval.data)

    @timeit
    def _load_routes(self):
        for conf_route in self._cfg.routes:
            if isinstance(conf_route, Config.CountryRoute) or isinstance(conf_route, Config.NetRoute):
                for r in conf_route.routes:
                    # Skip routes without interface
                    if r.interface is None:
                        logging.info(f"Skipping route {r.net} - no interface specified, will be used only for TTL calculation")
                        continue
                    self.add_route(r)
        logging.info("Country routes loaded")

    @timeit
    def __init__(self, app_config: Config.MySettings):
        self._cfg = app_config
        self._shutdown_event = threading.Event()

        self._routes_lock = threading.Lock()
        # Create a synchronized queue for route commands
        self._route_queue = queue.Queue()
        self._conntrack = Conntrack()
        # Start the route command processing thread
        self._route_thread = threading.Thread(target=self._process_route_commands_iproute2, daemon=True)
        self._route_thread.start()

        # Start the cleanup thread
        self._cleanup_interval = 10
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired_routes, daemon=True)
        self._cleanup_thread.start()
        self._route_tree = IntervalTree()
        self._load_routes()

    def __repr__(self):
        return f"Router({self._cfg.interfaces})"

    def on_a_record(self, record: ARecord) -> dict:
        selected_route: Optional[RouteObject] = None
        ttls = []
        ttls.append(record.ttl)
        
        # Check if the IP matches any network rules
        ip_int = int(ipaddress.IPv4Address(record.content))
        network_ttl = None
        
        for route in self._cfg.routes:
            if isinstance(route, Config.NetRoute):
                for net_route in route.routes:
                    if net_route.net_start <= ip_int <= net_route.net_end:
                        if net_route.ttl is not None:
                            network_ttl = net_route.ttl
                            break
                if network_ttl is not None:
                    break

        # Iterate over all routes in the config
        for route in self._cfg.routes:
            if isinstance(route, Config.DomainRoute) and route.match(record.name):
                new_route = route.build_route(record.content)
                if selected_route is None or new_route.weight > selected_route.weight:
                    selected_route = new_route

        if selected_route:
            # Calculate final TTL before adding route
            if network_ttl is not None:
                ttls.append(network_ttl)
            valid_ttls = [ttl for ttl in ttls if ttl is not None and ttl > 0]
            final_ttl = min(valid_ttls) if valid_ttls else None
            
            # Set the calculated TTL before adding route
            selected_route.ttl = final_ttl
            self.add_route(selected_route, immediate=True)
        else:
            ttls.append(self._cfg.domain_route_ttl)
            valid_ttls = [ttl for ttl in ttls if ttl is not None and ttl > 0]
            final_ttl = min(valid_ttls) if valid_ttls else None
            
        rv = {"ttl": final_ttl}
        return rv

    def stop(self):
        self._shutdown_event.set()

        if self._route_thread.is_alive():
            # Wait for the route processing thread to finish
            self._route_thread.join()

        # Wait for the cleanup thread to finish
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join()

        logging.info("Router shutdown complete")

    def __del__(self):
        self.stop()

    def _process_route_commands_iproute2(self):
        """
        Processes route commands from the queue one at a time using pyroute2.IPRoute.
        """
        from pyroute2 import IPRoute
        with IPRoute() as ipr:
            original_batch = IPBatch()
            remainder_batch = IPBatch()
            last_commit_time = time.time()
            max_size = original_batch.config['sndbuf']
            commit_interval = 0.02  # Commit at most every 0.1 seconds

            while not self._shutdown_event.is_set():
                original_batch.reset()
                remainder_batch.reset()
                current_batch_tree = IntervalTree()  # Track routes in this batch

                while True or not self._shutdown_event.is_set():
                    try:
                        cmd, route_spec = self._route_queue.get(timeout=0.01)
                        route_spec.update({'table': self._cfg.table})
                        remainder_batch.reset()
                        remainder_batch.route(cmd, **route_spec)
                        current_time = time.time()
                        time_since_last_commit = current_time - last_commit_time
                        if 'dst' in route_spec and 'dst_len' in route_spec:
                            # Create network object from route spec
                            network = ipaddress.IPv4Network(f"{route_spec['dst']}/{route_spec['dst_len']}")
                            # Calculate start and end of interval (inclusive range)
                            start = int(network.network_address)
                            end = int(network.broadcast_address) + 1  # +1 because IntervalTree end is exclusive

                            # Store route information in the interval
                            route_data = {
                                'network': network,
                            }

                            # Add to current batch tree
                            current_batch_tree[start:end] = route_data
                        potential_size = len(original_batch.batch) + len(
                            remainder_batch.batch)  # Use the proper method to get batch size
                        if potential_size >= max_size:
                            break
                        else:
                            remainder_batch.reset()
                            original_batch.route(cmd, **route_spec)
                        if time_since_last_commit >= commit_interval:
                            break
                            # Time to commit the batch

                    except queue.Empty:
                        break
                        # Check if we need to commit due to time, even if the queue was empty
                if len(original_batch.batch) > 0:
                    logging.info(f"Process batch {len(original_batch.batch)}")
                    ipr.sendto(original_batch.batch, (0, 0))
                if len(remainder_batch.batch) > 0:
                    logging.info(f"Process remainder {len(remainder_batch.batch)}")
                    ipr.sendto(remainder_batch.batch, (0, 0))
                if len(current_batch_tree) > 0:
                    self.remove_conntrack_entries_for_destination(current_batch_tree)
                last_commit_time = time.time()

    def _process_route_commands_netlink(self):
        """
        Processes all route commands from the queue in batches.
        """

        import netlink

        while not self._shutdown_event.is_set():
            last_cmd = None
            routes = []
            while True:
                try:
                    cmd, route_spec = self._route_queue.get(timeout=0.5)
                    route_spec.update({'table': self._cfg.table})
                    if last_cmd is None:
                        last_cmd = cmd
                    if cmd == last_cmd:
                        routes.append(route_spec)
                    if cmd != last_cmd or len(routes) > 200:
                        logging.info("Process batch")
                        if cmd == "add":
                            netlink.add_routes(routes)
                            routes.clear()
                        if cmd == "del":
                            netlink.delete_routes(routes)
                            routes.clear()

                except queue.Empty:
                    logging.debug("Queue Empty")
                    break

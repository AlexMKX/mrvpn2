from pyroute2 import IPRoute
import json
import logging, os
import dns_records
import signal

if not logging.getLogger().handlers:
    logging_level = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, logging_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

import nftables

from Config import MySettings
from Router import Router
import jinja2
import websockets
import asyncio
from lib import *

CONFIG: MySettings
ROUTER: Router

logger = logging.getLogger(__name__)


def apply_pbr():
    """
    Applies PBR (Policy-Based Routing) rules:
      1. Flushes the specified routing table.
      2. Removes existing rules for the specified table.
      3. Adds an IP rules (using pyroute2.IPRoute).
   """
    logging.debug("Applying PBR")
    clean_pbr()
    with IPRoute() as ipr:

        try:
            ipr.rule("add", fwmark=CONFIG.pbr_mark, table=CONFIG.table)
            logging.info(f"Added ip rule: fwmark=0x{CONFIG.pbr_mark:x}, table={CONFIG.table}")
        except Exception as e:
            logging.error(f"Error adding ip rule: {e}")
            raise
    env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
    env.filters['hex'] = lambda x: format(x, 'x')

    # Load the template from the environment
    template = env.get_template('templates/pbr.nft.j2')

    # For each interface, render the rules and apply them through the nftables API
    # Add table

    nft = nftables.Nftables()
    logging.debug(f"Rendering PBR for all interfaces: {CONFIG.interfaces}")

    rendered_ruleset = template.render(
        config=CONFIG)  # interfaces=CONFIG.interfaces, mark=CONFIG.pbr_mark, table=CONFIG.table)
    rc, output, error = nft.cmd(rendered_ruleset)
    if rc != 0:
        logging.error(f"Error applying NFT rules: {error} {rendered_ruleset}")
        raise Exception(f"Error applying NFT rules: {error} {rendered_ruleset}")
    logging.info("Applied NFT rules successfully")

    # Create a Jinja2 environment with the custom filter


def clean_pbr():
    nft = nftables.Nftables()
    nft.set_json_output(True)
    nft.set_handle_output(False)
    nft.set_terse_output(True)
    rc, output, error = nft.cmd("list tables")
    pbr_table = [x for x in output['data'] if 'table' in x.keys() and x['table']['name'] == 'ipt_server_pbr']
    if len(pbr_table) > 0:
        nft.cmd("delete table ipt_server_pbr")
    with IPRoute() as ipr:
        try:

            # Get existing rules for the specified table
            for x in range(0, len(ipr.get_rules(table=CONFIG.table))):
                # Remove the rule
                ipr.rule('del', table=CONFIG.table)
            logging.info(f"Removed existing rules for table {CONFIG.table}")
            if len(ipr.get_rules(table=CONFIG.table)) > 0:
                logging.warning(f"Unable to remove all existing rules for table {CONFIG.table}")
            # Flush the routing table
            ipr.flush_routes(table=CONFIG.table)
            logging.info(f"Flushed routing table {CONFIG.table}")
        except Exception as e:
            logging.error(f"Error flushing table or removing existing rules: {e}")


def main():
    global CONFIG, ROUTER
    config_file = os.getenv("CONFIG", "settings.yaml")
    CONFIG = MySettings.load(config_file)
    logging.debug(f"Loading config")
    apply_pbr()
    ROUTER = Router(CONFIG)

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    finally:
        # Ensure cleanup happens even if asyncio.run fails
        logging.info("Exiting application")


def process_a_record(record) -> dict:
    """
    record format: {'query': 'microsoft.com.', 'content': '20.236.44.162', 'name': 'microsoft.com.', 'type': 1}
    """
    global ROUTER
    return ROUTER.on_a_record(dns_records.ARecord(record))


async def echo(websocket: websockets.ServerConnection) -> None:
    """
    Handle WebSocket connections and process incoming messages.

    Message format: {'query': 'microsoft.com.', 'content': '20.236.44.162', 'name': 'microsoft.com.', 'type': 1}
    """
    async for message in websocket:
        try:
            msg = json.loads(message)
            logging.debug(f"Got message {msg}")
            rv = {}
            if msg['type'] == 1:
                rv = process_a_record(msg)
            await websocket.send(json.dumps(rv))
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON received: {message}")
            await websocket.send("Error: Invalid JSON")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await websocket.send("Error: Message processing failed")


async def shutdown(sig, stop_event):
    """Cleanup tasks tied to the service's shutdown."""
    logging.info(f"Received exit signal {sig.name}")
    stop_event.set()


async def async_main():
    # Create a task that can be cancelled
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Use asyncio's signal handler
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, stop_event)), None
        )

    # Start the websocket server
    server = await websockets.serve(echo, "0.0.0.0", CONFIG.ws_port, ping_timeout=30, ping_interval=30)

    try:
        # Instead of just waiting on the event, create a periodic task that checks the event
        # This ensures the event loop keeps running and can process signals
        while not stop_event.is_set():
            # Short sleep to allow other tasks and signal handlers to run
            await asyncio.sleep(0.1)
    finally:
        global ROUTER
        # Clean up resources
        logging.info("Cleaning up resources...")
        server.close()
        await server.wait_closed()
        clean_pbr()
        if ROUTER:
            ROUTER.stop()  # Ensure Router's __del__ method is called for cleanup

        logging.info("Server shutdown complete")


if __name__ == '__main__':
    import os

    if srv := os.environ.get('PYDEV', False):
        try:
            import pydevd_pycharm

            pydevd_pycharm.settrace(srv.split(':')[0], port=int(srv.split(':')[1]), stdoutToServer=True,
                                    stderrToServer=True,
                                    suspend=False)
        except Exception as e:
            logging.exception("Failed to connect to pydevd", exc_info=e)
    main()

# todo: add involved interfaces change monitoring and restart

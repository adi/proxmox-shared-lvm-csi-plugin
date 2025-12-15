"""
CSI Node entrypoint
"""
import os
import sys
import logging

from .grpc_server import serve_node


def setup_logging():
    """Setup logging configuration"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


def main():
    """Main entrypoint for CSI Node"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Proxmox CSI Node")

    # Get configuration from environment
    endpoint = os.getenv('CSI_ENDPOINT', 'unix:///csi/csi.sock')
    node_name = os.getenv('NODE_NAME')

    if not node_name:
        logger.error("NODE_NAME environment variable is required")
        sys.exit(1)

    try:
        # Start gRPC server
        serve_node(endpoint, node_name)

    except Exception as e:
        logger.error(f"Failed to start node server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

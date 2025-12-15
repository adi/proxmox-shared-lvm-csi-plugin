"""
CSI Controller entrypoint
"""
import os
import sys
import logging

from .config import load_config
from .grpc_server import serve_controller


def setup_logging():
    """Setup logging configuration"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


def main():
    """Main entrypoint for CSI Controller"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Proxmox CSI Controller")

    # Get configuration from environment
    endpoint = os.getenv('CSI_ENDPOINT', 'unix:///csi/csi.sock')
    config_path = os.getenv('CLOUD_CONFIG', '/etc/proxmox/config.yaml')

    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    try:
        # Load configuration
        config = load_config(config_path)
        logger.info(f"Loaded configuration with {len(config.clusters)} clusters")

        # Start gRPC server
        serve_controller(endpoint, config)

    except Exception as e:
        logger.error(f"Failed to start controller: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

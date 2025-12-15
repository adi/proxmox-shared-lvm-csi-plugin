"""
gRPC server setup for CSI driver
"""
import os
import logging
import signal
import time
from concurrent import futures
from typing import Optional
import grpc

from .csi_pb2_grpc import (
    add_IdentityServicer_to_server,
    add_ControllerServicer_to_server,
    add_NodeServicer_to_server
)
from .services.identity import IdentityService
from .services.controller import ControllerService
from .services.node import NodeService
from .config import CSIConfig


logger = logging.getLogger(__name__)


def parse_endpoint(endpoint: str) -> tuple[str, str]:
    """
    Parse CSI endpoint into protocol and address

    Args:
        endpoint: Endpoint string (e.g., unix:///csi/csi.sock)

    Returns:
        Tuple of (protocol, address)

    Raises:
        ValueError: If endpoint format is invalid
    """
    if '://' not in endpoint:
        raise ValueError(f"Invalid endpoint format: {endpoint}")

    protocol, address = endpoint.split('://', 1)

    if protocol not in ['unix', 'tcp']:
        raise ValueError(f"Unsupported protocol: {protocol}")

    return protocol, address


def cleanup_socket(address: str):
    """Remove existing unix socket file"""
    if os.path.exists(address):
        logger.info(f"Removing existing socket: {address}")
        os.unlink(address)


def setup_signal_handlers(server: grpc.Server):
    """Setup graceful shutdown on SIGTERM/SIGINT"""
    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        server.stop(grace=10)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


def serve_controller(endpoint: str, config: CSIConfig):
    """
    Start CSI Controller gRPC server

    Args:
        endpoint: gRPC endpoint (e.g., unix:///csi/csi.sock)
        config: CSI configuration
    """
    logger.info(f"Starting CSI Controller server on {endpoint}")

    protocol, address = parse_endpoint(endpoint)

    # Cleanup unix socket if exists
    if protocol == 'unix':
        # Create directory if needed
        socket_dir = os.path.dirname(address)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)
        cleanup_socket(address)

    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 16 * 1024 * 1024),  # 16MB
            ('grpc.max_receive_message_length', 16 * 1024 * 1024),  # 16MB
        ]
    )

    # Add services
    identity_service = IdentityService()
    controller_service = ControllerService(config)

    add_IdentityServicer_to_server(identity_service, server)
    add_ControllerServicer_to_server(controller_service, server)

    # Bind to endpoint
    if protocol == 'unix':
        server.add_insecure_port(f'unix:{address}')
    else:
        server.add_insecure_port(address)

    # Start server
    server.start()
    logger.info("CSI Controller server started successfully")

    # Setup signal handlers
    setup_signal_handlers(server)

    # Wait for termination
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.stop(grace=10)
        if protocol == 'unix':
            cleanup_socket(address)
        logger.info("CSI Controller server stopped")


def serve_node(endpoint: str, node_name: str):
    """
    Start CSI Node gRPC server

    Args:
        endpoint: gRPC endpoint (e.g., unix:///csi/csi.sock)
        node_name: Kubernetes node name
    """
    logger.info(f"Starting CSI Node server on {endpoint} for node {node_name}")

    protocol, address = parse_endpoint(endpoint)

    # Cleanup unix socket if exists
    if protocol == 'unix':
        # Create directory if needed
        socket_dir = os.path.dirname(address)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)
        cleanup_socket(address)

    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 16 * 1024 * 1024),  # 16MB
            ('grpc.max_receive_message_length', 16 * 1024 * 1024),  # 16MB
        ]
    )

    # Add services
    identity_service = IdentityService()
    node_service = NodeService(node_name)

    add_IdentityServicer_to_server(identity_service, server)
    add_NodeServicer_to_server(node_service, server)

    # Bind to endpoint
    if protocol == 'unix':
        server.add_insecure_port(f'unix:{address}')
    else:
        server.add_insecure_port(address)

    # Start server
    server.start()
    logger.info("CSI Node server started successfully")

    # Setup signal handlers
    setup_signal_handlers(server)

    # Wait for termination
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.stop(grace=10)
        if protocol == 'unix':
            cleanup_socket(address)
        logger.info("CSI Node server stopped")

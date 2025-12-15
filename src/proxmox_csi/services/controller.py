"""
CSI Controller Service Implementation
"""
import logging
import grpc
from typing import Dict
from ..csi_pb2 import (
    CreateVolumeResponse,
    DeleteVolumeResponse,
    ControllerPublishVolumeResponse,
    ControllerUnpublishVolumeResponse,
    ControllerExpandVolumeResponse,
    ControllerGetCapabilitiesResponse,
    Volume,
    ControllerServiceCapability
)
from ..csi_pb2_grpc import ControllerServicer
from ..proxmox.client import ProxmoxClient
from ..proxmox.operations import (
    create_volume,
    delete_volume,
    attach_volume,
    detach_volume,
    check_existing_attachments,
    expand_volume
)
from ..volume.volume_id import parse_volume_id
from ..config import CSIConfig
from ..constants import (
    DRIVER_NAME,
    MIN_VOLUME_SIZE,
    DEFAULT_VOLUME_SIZE
)


logger = logging.getLogger(__name__)


class ControllerService(ControllerServicer):
    """CSI Controller Server"""

    def __init__(self, config: CSIConfig):
        self.config = config
        self.clients: Dict[str, ProxmoxClient] = {}

        # Initialize Proxmox clients for each cluster
        for cluster in config.clusters:
            self.clients[cluster.region] = ProxmoxClient(
                url=cluster.url,
                token_id=cluster.token_id,
                token_secret=cluster.token_secret,
                insecure=cluster.insecure
            )

        logger.info(f"Controller service initialized with {len(self.clients)} clusters")

    def CreateVolume(self, request, context):
        """Create volume"""
        name = request.name
        if not name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Name must be provided")

        logger.info(f"CreateVolume: {name}")
        logger.debug(f"CreateVolume request: name={name}, parameters={dict(request.parameters or {})}")

        # Get size
        capacity_range = request.capacity_range
        if capacity_range:
            size_bytes = max(capacity_range.required_bytes, MIN_VOLUME_SIZE)
        else:
            size_bytes = DEFAULT_VOLUME_SIZE

        logger.debug(f"CreateVolume: size_bytes={size_bytes}, capacity_range={capacity_range}")

        # Get parameters
        params = request.parameters or {}
        storage = params.get('storage')
        if not storage:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "storage parameter required")

        logger.debug(f"CreateVolume: storage={storage}, all_params={params}")

        # Get region/zone from topology (simplified - use first cluster/node)
        region = list(self.clients.keys())[0]
        client = self.clients[region]
        nodes = client.get_nodes()
        if not nodes:
            context.abort(grpc.StatusCode.INTERNAL, "No nodes available")
        zone = nodes[0]

        # Create new volume
        logger.info(f"CreateVolume: creating new volume on storage={storage}, size={size_bytes}")
        volume_id = create_volume(client, region, zone, storage, name, size_bytes)

        # Return volume
        volume = Volume(
            volume_id=volume_id,
            capacity_bytes=size_bytes
        )

        logger.info(f"Volume created: {volume_id}")
        return CreateVolumeResponse(volume=volume)

    def DeleteVolume(self, request, context):
        """Delete volume"""
        volume_id = request.volume_id
        if not volume_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "VolumeID must be provided")

        logger.info(f"DeleteVolume: {volume_id}")

        try:
            region, zone, storage, disk = parse_volume_id(volume_id)
            client = self.clients.get(region)
            if not client:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Region {region} not found")

            delete_volume(client, volume_id)

            logger.info(f"Volume deleted: {volume_id}")
            return DeleteVolumeResponse()

        except Exception as e:
            logger.error(f"DeleteVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def ControllerPublishVolume(self, request, context):
        """Attach volume to node"""
        volume_id = request.volume_id
        node_id = request.node_id

        if not volume_id or not node_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "VolumeID and NodeID required")

        logger.info(f"ControllerPublishVolume: {volume_id} to {node_id}")

        try:
            region, zone, storage, disk = parse_volume_id(volume_id)
            client = self.clients.get(region)
            if not client:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Region {region} not found")

            # Discover VMID from node_id (Kubernetes node name)
            logger.debug(f"ControllerPublishVolume: discovering VM ID for node {node_id}")

            # Try to parse as integer first (for explicit VMID)
            try:
                vmid = int(node_id)
                logger.info(f"ControllerPublishVolume: using explicit VMID {vmid}")
            except ValueError:
                # Node name provided, discover VM from Proxmox
                vm_info = client.find_vm_by_name(node_id)
                if vm_info is None:
                    context.abort(
                        grpc.StatusCode.NOT_FOUND,
                        f"No VM found with name '{node_id}' in Proxmox cluster"
                    )
                vmid, vm_node = vm_info
                logger.info(f"ControllerPublishVolume: discovered VM {vmid} on node {vm_node} for Kubernetes node {node_id}")

            # CRITICAL: Split-brain protection
            existing_vmid, existing_lun = check_existing_attachments(client, region, storage, disk)

            if existing_vmid is not None:
                if existing_vmid == vmid:
                    # Already attached to this VM (idempotent)
                    logger.info(f"Volume {volume_id} already attached to VM {vmid}")
                    wwn = f"{existing_lun:02d}".encode('utf-8').hex()
                    return ControllerPublishVolumeResponse(
                        publish_context={
                            'DevicePath': f'/dev/disk/by-id/wwn-0x{wwn}',
                            'lun': str(existing_lun)
                        }
                    )
                else:
                    # Attached to different VM - SPLIT-BRAIN PROTECTION
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        f"Volume {volume_id} already attached to VM {existing_vmid}"
                    )

            # Attach volume
            publish_context = attach_volume(client, vmid, volume_id)

            logger.info(f"Volume {volume_id} attached to VM {vmid}")
            return ControllerPublishVolumeResponse(publish_context=publish_context)

        except Exception as e:
            logger.error(f"ControllerPublishVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def ControllerUnpublishVolume(self, request, context):
        """Detach volume from node"""
        volume_id = request.volume_id
        node_id = request.node_id

        if not volume_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "VolumeID required")

        logger.info(f"ControllerUnpublishVolume: {volume_id} from {node_id}")

        try:
            region, zone, storage, disk = parse_volume_id(volume_id)
            client = self.clients.get(region)
            if not client:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Region {region} not found")

            # Discover VMID from node_id (Kubernetes node name)
            if not node_id:
                # If node_id not provided, search for which VM has the volume attached
                logger.warning(f"ControllerUnpublishVolume: no node_id provided, searching for attachment")
                existing_vmid, _ = check_existing_attachments(client, region, storage, disk)
                if existing_vmid is None:
                    logger.info(f"ControllerUnpublishVolume: volume {volume_id} not attached anywhere")
                    return ControllerUnpublishVolumeResponse()
                vmid = existing_vmid
            else:
                logger.debug(f"ControllerUnpublishVolume: discovering VM ID for node {node_id}")
                try:
                    vmid = int(node_id)
                    logger.info(f"ControllerUnpublishVolume: using explicit VMID {vmid}")
                except ValueError:
                    vm_info = client.find_vm_by_name(node_id)
                    if vm_info is None:
                        # For unpublish, if VM not found, it's likely already deleted
                        # This is idempotent, so just return success
                        logger.warning(f"ControllerUnpublishVolume: VM '{node_id}' not found, assuming already detached")
                        return ControllerUnpublishVolumeResponse()
                    vmid, vm_node = vm_info
                    logger.info(f"ControllerUnpublishVolume: discovered VM {vmid} on node {vm_node}")

            # Detach volume
            detach_volume(client, vmid, volume_id)

            logger.info(f"Volume {volume_id} detached from VM {vmid}")
            return ControllerUnpublishVolumeResponse()

        except Exception as e:
            logger.error(f"ControllerUnpublishVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def ControllerExpandVolume(self, request, context):
        """Expand volume"""
        volume_id = request.volume_id
        if not volume_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "VolumeID required")

        capacity_range = request.capacity_range
        if not capacity_range:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "CapacityRange required")

        new_size = capacity_range.required_bytes

        logger.info(f"ControllerExpandVolume: {volume_id} to {new_size} bytes")

        try:
            region, zone, storage, disk = parse_volume_id(volume_id)
            client = self.clients.get(region)
            if not client:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Region {region} not found")

            # For expansion, volume must be attached. Find which VM it's attached to.
            logger.debug(f"ControllerExpandVolume: finding which VM has volume {volume_id} attached")
            existing_vmid, _ = check_existing_attachments(client, region, storage, disk)
            if existing_vmid is None:
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"Volume {volume_id} must be attached to a VM to expand"
                )

            logger.info(f"ControllerExpandVolume: volume attached to VM {existing_vmid}")
            expand_volume(client, existing_vmid, volume_id, new_size)

            logger.info(f"Volume {volume_id} expanded to {new_size} bytes")
            return ControllerExpandVolumeResponse(
                capacity_bytes=new_size,
                node_expansion_required=True
            )

        except Exception as e:
            logger.error(f"ControllerExpandVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def ControllerGetCapabilities(self, request, context):
        """Return controller capabilities"""
        logger.debug("ControllerGetCapabilities called")

        capabilities = [
            ControllerServiceCapability(
                rpc=ControllerServiceCapability.RPC(
                    type=ControllerServiceCapability.RPC.CREATE_DELETE_VOLUME
                )
            ),
            ControllerServiceCapability(
                rpc=ControllerServiceCapability.RPC(
                    type=ControllerServiceCapability.RPC.PUBLISH_UNPUBLISH_VOLUME
                )
            ),
            ControllerServiceCapability(
                rpc=ControllerServiceCapability.RPC(
                    type=ControllerServiceCapability.RPC.EXPAND_VOLUME
                )
            ),
        ]

        return ControllerGetCapabilitiesResponse(capabilities=capabilities)

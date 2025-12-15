"""
CSI Node Service Implementation
"""
import logging
import grpc
import os
from ..csi_pb2 import (
    NodeStageVolumeResponse,
    NodeUnstageVolumeResponse,
    NodePublishVolumeResponse,
    NodeUnpublishVolumeResponse,
    NodeExpandVolumeResponse,
    NodeGetCapabilitiesResponse,
    NodeGetInfoResponse,
    NodeGetVolumeStatsResponse,
    NodeServiceCapability,
    VolumeCapability
)
from ..csi_pb2_grpc import NodeServicer
from ..device.discovery import discover_device_by_wwn, get_device_from_mount
from ..filesystem.format import format_device, check_filesystem
from ..filesystem.mount import mount_device, unmount_path, bind_mount, is_mounted
from ..filesystem.resize import resize_filesystem, get_filesystem_type
from ..constants import (
    DRIVER_NAME,
    MAX_VOLUMES_PER_NODE,
    DEFAULT_FS_TYPE
)


logger = logging.getLogger(__name__)


class NodeService(NodeServicer):
    """CSI Node Server"""

    def __init__(self, node_name: str):
        self.node_name = node_name
        logger.info(f"Node service initialized for node: {node_name}")

    def NodeStageVolume(self, request, context):
        """Stage volume (format and mount to staging path)"""
        volume_id = request.volume_id
        staging_path = request.staging_target_path
        publish_context = request.publish_context

        if not volume_id or not staging_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         "VolumeID and StagingTargetPath required")

        logger.info(f"NodeStageVolume: {volume_id} to {staging_path}")

        # Check if block volume
        volume_capability = request.volume_capability
        if volume_capability and volume_capability.HasField('block'):
            # Raw block volume - skip staging
            logger.info("Raw block volume, skipping staging")
            return NodeStageVolumeResponse()

        try:
            # Extract WWN from publish context
            device_path_wwn = publish_context.get('DevicePath', '')
            if not device_path_wwn:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "DevicePath not provided")

            # Extract WWN hex string
            wwn = device_path_wwn.split('wwn-0x')[1] if 'wwn-0x' in device_path_wwn else ''
            if not wwn:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid DevicePath format")

            # Discover device
            device_path = discover_device_by_wwn(wwn)
            logger.info(f"Device discovered: {device_path}")

            # Get filesystem type
            fstype = DEFAULT_FS_TYPE
            if volume_capability and volume_capability.HasField('mount'):
                if volume_capability.mount.fs_type:
                    fstype = volume_capability.mount.fs_type

            # Check if already formatted
            existing_fs = check_filesystem(device_path)
            if not existing_fs:
                # Format device
                format_device(device_path, fstype)
                logger.info(f"Device {device_path} formatted as {fstype}")

            # Mount to staging path
            if not is_mounted(staging_path):
                mount_device(device_path, staging_path, fstype)
                logger.info(f"Device mounted to {staging_path}")

            logger.info(f"NodeStageVolume completed for {volume_id}")
            return NodeStageVolumeResponse()

        except Exception as e:
            logger.error(f"NodeStageVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def NodeUnstageVolume(self, request, context):
        """Unstage volume (unmount from staging path)"""
        volume_id = request.volume_id
        staging_path = request.staging_target_path

        if not volume_id or not staging_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         "VolumeID and StagingTargetPath required")

        logger.info(f"NodeUnstageVolume: {volume_id} from {staging_path}")

        try:
            # Skip if raw block device (check path)
            if '/volumeDevices/' in staging_path:
                logger.info("Raw block device, skipping unstaging")
                return NodeUnstageVolumeResponse()

            # Unmount
            if is_mounted(staging_path):
                unmount_path(staging_path)
                logger.info(f"Path {staging_path} unmounted")

            logger.info(f"NodeUnstageVolume completed for {volume_id}")
            return NodeUnstageVolumeResponse()

        except Exception as e:
            logger.error(f"NodeUnstageVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def NodePublishVolume(self, request, context):
        """Publish volume (bind mount to pod path)"""
        volume_id = request.volume_id
        staging_path = request.staging_target_path
        target_path = request.target_path
        readonly = request.readonly

        if not volume_id or not target_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         "VolumeID and TargetPath required")

        logger.info(f"NodePublishVolume: {volume_id} to {target_path}")

        try:
            volume_capability = request.volume_capability

            # Check if block volume
            if volume_capability and volume_capability.HasField('block'):
                # Raw block - bind mount device directly
                publish_context = request.publish_context
                device_path_wwn = publish_context.get('DevicePath', '')
                wwn = device_path_wwn.split('wwn-0x')[1] if 'wwn-0x' in device_path_wwn else ''
                device_path = discover_device_by_wwn(wwn)

                logger.info(f"Binding raw block device {device_path} to {target_path}")
                bind_mount(device_path, target_path, readonly)
            else:
                # Filesystem - bind mount from staging
                if not staging_path:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                                 "StagingTargetPath required for filesystem volume")

                logger.info(f"Binding {staging_path} to {target_path}")
                bind_mount(staging_path, target_path, readonly)

            logger.info(f"NodePublishVolume completed for {volume_id}")
            return NodePublishVolumeResponse()

        except Exception as e:
            logger.error(f"NodePublishVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def NodeUnpublishVolume(self, request, context):
        """Unpublish volume (unmount from pod path)"""
        volume_id = request.volume_id
        target_path = request.target_path

        if not volume_id or not target_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         "VolumeID and TargetPath required")

        logger.info(f"NodeUnpublishVolume: {volume_id} from {target_path}")

        try:
            if is_mounted(target_path):
                unmount_path(target_path)
                logger.info(f"Path {target_path} unmounted")

            logger.info(f"NodeUnpublishVolume completed for {volume_id}")
            return NodeUnpublishVolumeResponse()

        except Exception as e:
            logger.error(f"NodeUnpublishVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def NodeExpandVolume(self, request, context):
        """Expand filesystem on node"""
        volume_id = request.volume_id
        volume_path = request.volume_path

        if not volume_id or not volume_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         "VolumeID and VolumePath required")

        logger.info(f"NodeExpandVolume: {volume_id} at {volume_path}")

        try:
            # Check if block volume
            volume_capability = request.volume_capability
            if volume_capability and volume_capability.HasField('block'):
                # No filesystem resize needed for raw block
                logger.info("Raw block volume, no resize needed")
                return NodeExpandVolumeResponse()

            # Get device from mount
            device_path = get_device_from_mount(volume_path)
            if not device_path:
                context.abort(grpc.StatusCode.INTERNAL,
                             f"Cannot find device for mount {volume_path}")

            # Get filesystem type
            fstype = get_filesystem_type(device_path)

            # Resize filesystem
            resize_filesystem(device_path, volume_path, fstype)

            logger.info(f"NodeExpandVolume completed for {volume_id}")
            return NodeExpandVolumeResponse()

        except Exception as e:
            logger.error(f"NodeExpandVolume failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def NodeGetCapabilities(self, request, context):
        """Return node capabilities"""
        logger.debug("NodeGetCapabilities called")

        capabilities = [
            NodeServiceCapability(
                rpc=NodeServiceCapability.RPC(
                    type=NodeServiceCapability.RPC.STAGE_UNSTAGE_VOLUME
                )
            ),
            NodeServiceCapability(
                rpc=NodeServiceCapability.RPC(
                    type=NodeServiceCapability.RPC.EXPAND_VOLUME
                )
            ),
            NodeServiceCapability(
                rpc=NodeServiceCapability.RPC(
                    type=NodeServiceCapability.RPC.GET_VOLUME_STATS
                )
            ),
        ]

        return NodeGetCapabilitiesResponse(capabilities=capabilities)

    def NodeGetInfo(self, request, context):
        """Return node information"""
        logger.debug(f"NodeGetInfo called for {self.node_name}")

        return NodeGetInfoResponse(
            node_id=self.node_name,
            max_volumes_per_node=MAX_VOLUMES_PER_NODE
        )

    def NodeGetVolumeStats(self, request, context):
        """Return volume statistics"""
        volume_id = request.volume_id
        volume_path = request.volume_path

        logger.debug(f"NodeGetVolumeStats: {volume_id} at {volume_path}")

        try:
            # Get filesystem stats
            stat = os.statvfs(volume_path)

            total_bytes = stat.f_blocks * stat.f_frsize
            available_bytes = stat.f_bavail * stat.f_frsize
            used_bytes = total_bytes - available_bytes

            total_inodes = stat.f_files
            available_inodes = stat.f_favail
            used_inodes = total_inodes - available_inodes

            return NodeGetVolumeStatsResponse(
                usage=[
                    NodeGetVolumeStatsResponse.VolumeUsage(
                        unit=NodeGetVolumeStatsResponse.VolumeUsage.BYTES,
                        total=total_bytes,
                        available=available_bytes,
                        used=used_bytes
                    ),
                    NodeGetVolumeStatsResponse.VolumeUsage(
                        unit=NodeGetVolumeStatsResponse.VolumeUsage.INODES,
                        total=total_inodes,
                        available=available_inodes,
                        used=used_inodes
                    )
                ]
            )

        except Exception as e:
            logger.error(f"NodeGetVolumeStats failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

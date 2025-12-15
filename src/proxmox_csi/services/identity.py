"""
CSI Identity Service Implementation
"""
import logging
from google.protobuf.wrappers_pb2 import BoolValue
from ..csi_pb2 import (
    GetPluginInfoResponse,
    GetPluginCapabilitiesResponse,
    ProbeResponse,
    PluginCapability
)
from ..csi_pb2_grpc import IdentityServicer
from ..constants import DRIVER_NAME, DRIVER_VERSION


logger = logging.getLogger(__name__)


class IdentityService(IdentityServicer):
    """CSI Identity Server"""

    def GetPluginInfo(self, request, context):
        """
        Return plugin information

        Returns driver name and version
        """
        logger.debug("GetPluginInfo called")

        return GetPluginInfoResponse(
            name=DRIVER_NAME,
            vendor_version=DRIVER_VERSION
        )

    def GetPluginCapabilities(self, request, context):
        """
        Return plugin capabilities

        Advertises:
        - CONTROLLER_SERVICE
        - VOLUME_ACCESSIBILITY_CONSTRAINTS
        """
        logger.debug("GetPluginCapabilities called")

        capabilities = [
            PluginCapability(
                service=PluginCapability.Service(
                    type=PluginCapability.Service.CONTROLLER_SERVICE
                )
            ),
            PluginCapability(
                volume_expansion=PluginCapability.VolumeExpansion(
                    type=PluginCapability.VolumeExpansion.ONLINE
                )
            )
        ]

        return GetPluginCapabilitiesResponse(capabilities=capabilities)

    def Probe(self, request, context):
        """
        Health check

        Always returns ready
        """
        logger.debug("Probe called")

        return ProbeResponse(ready=BoolValue(value=True))

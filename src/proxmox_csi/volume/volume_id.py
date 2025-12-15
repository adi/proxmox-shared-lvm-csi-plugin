"""
Volume ID parsing and generation

Volume ID format: region/zone/storage/disk-name
Example: cluster-1/pve-1/alletra-vg/vm-9999-pvc-abc123
"""
from typing import Tuple
from ..constants import VOLUME_ID_SEPARATOR, VOLUME_ID_PARTS


class VolumeID:
    """Volume ID handler"""

    def __init__(self, region: str, zone: str, storage: str, disk: str):
        self.region = region
        self.zone = zone
        self.storage = storage
        self.disk = disk

    def __str__(self) -> str:
        """Return volume ID string"""
        return f"{self.region}{VOLUME_ID_SEPARATOR}{self.zone}{VOLUME_ID_SEPARATOR}{self.storage}{VOLUME_ID_SEPARATOR}{self.disk}"

    @classmethod
    def from_string(cls, volume_id: str) -> 'VolumeID':
        """
        Parse volume ID from string

        Args:
            volume_id: Volume ID string in format region/zone/storage/disk

        Returns:
            VolumeID object

        Raises:
            ValueError: If volume ID format is invalid
        """
        parts = volume_id.split(VOLUME_ID_SEPARATOR)
        if len(parts) != VOLUME_ID_PARTS:
            raise ValueError(f"Invalid volume ID format: {volume_id}, expected {VOLUME_ID_PARTS} parts")

        return cls(
            region=parts[0],
            zone=parts[1],
            storage=parts[2],
            disk=parts[3]
        )

    @classmethod
    def create(cls, region: str, zone: str, storage: str, pvc_name: str, vmid: int = 9999) -> 'VolumeID':
        """
        Create new volume ID

        Args:
            region: Cluster region
            zone: Node/zone name
            storage: Storage ID
            pvc_name: PVC name
            vmid: VM ID for volume storage (default: 9999)

        Returns:
            VolumeID object
        """
        disk_name = f"vm-{vmid}-{pvc_name}"
        return cls(region=region, zone=zone, storage=storage, disk=disk_name)

    def to_tuple(self) -> Tuple[str, str, str, str]:
        """Return volume ID as tuple (region, zone, storage, disk)"""
        return (self.region, self.zone, self.storage, self.disk)


def parse_volume_id(volume_id: str) -> Tuple[str, str, str, str]:
    """
    Parse volume ID string into components

    Args:
        volume_id: Volume ID string

    Returns:
        Tuple of (region, zone, storage, disk)
    """
    vid = VolumeID.from_string(volume_id)
    return vid.to_tuple()


def create_volume_id(region: str, zone: str, storage: str, pvc_name: str, vmid: int = 9999) -> str:
    """
    Create volume ID string

    Args:
        region: Cluster region
        zone: Node/zone name
        storage: Storage ID
        pvc_name: PVC name
        vmid: VM ID (default: 9999)

    Returns:
        Volume ID string
    """
    vid = VolumeID.create(region, zone, storage, pvc_name, vmid)
    return str(vid)

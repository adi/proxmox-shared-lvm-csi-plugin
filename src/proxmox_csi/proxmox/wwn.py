"""
WWN (World Wide Name) and LUN management for SCSI devices
"""
from typing import Optional, Dict
from ..constants import LUN_MIN, LUN_MAX


def calculate_wwn(lun: int) -> str:
    """
    Calculate WWN identifier for LUN

    Format: hex(PVC-ID{LUN:02d})

    Args:
        lun: LUN number (1-29)

    Returns:
        WWN hex string (without 0x prefix)

    Example:
        >>> calculate_wwn(5)
        '5043432d49443035'  # hex of "PVC-ID05"
    """
    identifier = f"PVC-ID{lun:02d}"
    return identifier.encode('utf-8').hex()


def find_free_lun(scsi_disks: Dict[str, str], min_lun: int = LUN_MIN,
                 max_lun: int = LUN_MAX) -> Optional[int]:
    """
    Find first available LUN

    Args:
        scsi_disks: Dictionary of existing SCSI disks {device: disk_string}
        min_lun: Minimum LUN number (default: 1)
        max_lun: Maximum LUN number (default: 29)

    Returns:
        First available LUN number, or None if all LUNs are used
    """
    used_luns = set()

    for device in scsi_disks.keys():
        if device.startswith('scsi'):
            try:
                lun_num = int(device[4:])  # Extract number from "scsi5"
                used_luns.add(lun_num)
            except ValueError:
                continue

    for lun in range(min_lun, max_lun + 1):
        if lun not in used_luns:
            return lun

    return None


def is_disk_attached(scsi_disks: Dict[str, str], disk_name: str) -> Optional[int]:
    """
    Check if disk is attached and return LUN

    Args:
        scsi_disks: Dictionary of existing SCSI disks
        disk_name: Disk name to search for

    Returns:
        LUN number if attached, None otherwise
    """
    for device, disk_string in scsi_disks.items():
        if disk_name in disk_string and device.startswith('scsi'):
            try:
                lun = int(device[4:])
                return lun
            except ValueError:
                continue

    return None

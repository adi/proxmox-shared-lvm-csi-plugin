"""
WWN-based device discovery via sysfs scanning
"""
import os
import time
import logging
from typing import Optional
from ..constants import SCSI_DEVICES_PATH, DEVICE_DISCOVERY_TIMEOUT, DEVICE_DISCOVERY_INTERVAL


logger = logging.getLogger(__name__)


def discover_device_by_wwn(wwn: str, timeout: int = DEVICE_DISCOVERY_TIMEOUT) -> str:
    """
    Discover block device by WWN identifier

    Scans /sys/bus/scsi/devices for matching WWN.
    Retries for specified timeout with short intervals.

    Args:
        wwn: WWN hex string (without 0x prefix)
        timeout: Timeout in seconds (default: 10)

    Returns:
        Device path (e.g., /dev/sda)

    Raises:
        Exception: If device not found after timeout
    """
    logger.info(f"Discovering device with WWN {wwn}")

    max_retries = int(timeout / DEVICE_DISCOVERY_INTERVAL)

    for attempt in range(max_retries):
        device_path = scan_scsi_devices_for_wwn(wwn)
        if device_path:
            logger.info(f"Device found: {device_path} for WWN {wwn}")
            return device_path

        time.sleep(DEVICE_DISCOVERY_INTERVAL)

    raise Exception(f"Device with WWN {wwn} not found after {timeout}s")


def scan_scsi_devices_for_wwn(target_wwn: str) -> Optional[str]:
    """
    Scan SCSI devices for matching WWN

    Args:
        target_wwn: Target WWN hex string

    Returns:
        Device path if found, None otherwise
    """
    if not os.path.exists(SCSI_DEVICES_PATH):
        return None

    try:
        for device_dir in os.listdir(SCSI_DEVICES_PATH):
            device_path = os.path.join(SCSI_DEVICES_PATH, device_dir)

            # Check if this is a QEMU device
            vendor_file = os.path.join(device_path, 'vendor')
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, 'r') as f:
                        vendor = f.read().strip()
                        if vendor.upper() != 'QEMU':
                            continue
                except:
                    continue

            # Check WWN matches
            wwid_file = os.path.join(device_path, 'wwid')
            if os.path.exists(wwid_file):
                try:
                    with open(wwid_file, 'r') as f:
                        wwid = f.read().strip()
                        if not wwid.startswith('naa.'):
                            continue

                        # Extract WWN (remove 'naa.' prefix)
                        wwn = wwid[4:]
                        if wwn == target_wwn:
                            # Found matching device, get block device name
                            block_dir = os.path.join(device_path, 'block')
                            if os.path.exists(block_dir):
                                block_devices = os.listdir(block_dir)
                                if block_devices:
                                    return f'/dev/{block_devices[0]}'
                except:
                    continue

    except Exception as e:
        logger.error(f"Error scanning SCSI devices: {e}")

    return None


def get_device_from_mount(mount_path: str) -> Optional[str]:
    """
    Get device path from mount path

    Args:
        mount_path: Mount path

    Returns:
        Device path or None
    """
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == mount_path:
                    return parts[0]
    except Exception as e:
        logger.error(f"Error reading /proc/mounts: {e}")

    return None

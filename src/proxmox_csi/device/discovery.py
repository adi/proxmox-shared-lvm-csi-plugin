"""
WWN-based device discovery via sysfs scanning
"""
import os
import stat
import subprocess
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


def get_block_device_from_special(path: str) -> Optional[str]:
    """
    Resolve a block special file (e.g. a bind-mounted raw block volume)
    to its /dev/<name> device path

    Args:
        path: Path to a block special file

    Returns:
        Device path if path is a block device, None otherwise
    """
    try:
        st = os.stat(path)
        if not stat.S_ISBLK(st.st_mode):
            return None
        major, minor = os.major(st.st_rdev), os.minor(st.st_rdev)
        sys_path = os.path.realpath(f'/sys/dev/block/{major}:{minor}')
        return f'/dev/{os.path.basename(sys_path)}'
    except OSError:
        return None


def is_device_in_use(device_path: str) -> bool:
    """
    Check whether a block device still backs any mount or bind mount

    Args:
        device_path: Device path (e.g., /dev/sdb)

    Returns:
        True if the device is mounted or its /dev entry is bind-mounted
    """
    try:
        st = os.stat(device_path)
        if not stat.S_ISBLK(st.st_mode):
            return False
        majmin = f'{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}'
    except OSError:
        return False

    device_name = os.path.basename(os.path.realpath(device_path))

    try:
        with open('/proc/self/mountinfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) < 5:
                    continue
                # parts[2] is the mount's device major:minor (filesystem
                # mounts), parts[3] is the root within the source filesystem
                # (the device name for a bind-mounted /dev entry)
                if parts[2] == majmin or parts[3] == f'/{device_name}':
                    return True
    except OSError:
        pass

    return False


def remove_scsi_device(device_path: str) -> None:
    """
    Flush and delete a SCSI block device from the kernel

    Must run after the last unmount and before ControllerUnpublishVolume
    detaches the disk from the VM: flushing prevents dirty buffers from
    being lost when the LUN disappears, and deleting the device prevents
    a stale /dev entry (with the old WWN still in sysfs) from confusing
    later discovery.

    Args:
        device_path: Device path (e.g., /dev/sdb)

    Raises:
        Exception: If the device cannot be removed - the caller must fail
        the RPC so kubelet retries before the controller detaches the disk
    """
    device_name = os.path.basename(os.path.realpath(device_path))

    # Flush page cache and dirty buffers (best effort)
    try:
        subprocess.run(['blockdev', '--flushbufs', device_path],
                      capture_output=True, check=False, timeout=30)
    except Exception as e:
        logger.warning(f"blockdev --flushbufs failed (ignored): {e}")

    delete_path = f'/sys/block/{device_name}/device/delete'
    try:
        with open(delete_path, 'w') as f:
            f.write('1')
    except OSError as e:
        raise Exception(f"Failed to remove SCSI device {device_name}: {e}")

    logger.info(f"SCSI device {device_name} removed")


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

"""
Filesystem formatting utilities
"""
import subprocess
import logging
from typing import Optional, Dict
from ..constants import FS_TYPE_EXT4, FS_TYPE_XFS


logger = logging.getLogger(__name__)


def format_device(device_path: str, fstype: str = FS_TYPE_EXT4,
                 options: Optional[Dict] = None) -> bool:
    """
    Format block device with specified filesystem

    Args:
        device_path: Device path (e.g., /dev/sda)
        fstype: Filesystem type (ext4 or xfs)
        options: Format options (block_size, inode_size)

    Returns:
        True if successful

    Raises:
        Exception: If formatting fails
    """
    logger.info(f"Formatting {device_path} as {fstype}")

    if fstype == FS_TYPE_EXT4:
        cmd = ['mkfs.ext4', '-F']
        if options:
            if 'block_size' in options:
                cmd.extend(['-b', str(options['block_size'])])
            if 'inode_size' in options:
                cmd.extend(['-I', str(options['inode_size'])])
        cmd.append(device_path)

    elif fstype == FS_TYPE_XFS:
        cmd = ['mkfs.xfs', '-f']
        if options:
            if 'block_size' in options:
                cmd.extend(['-b', f"size={options['block_size']}"])
            if 'inode_size' in options:
                cmd.extend(['-i', f"size={options['inode_size']}"])
        cmd.append(device_path)

    else:
        raise ValueError(f"Unsupported filesystem type: {fstype}")

    logger.debug(f"Format command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to format {device_path}: {result.stderr}")

    logger.info(f"Device {device_path} formatted successfully as {fstype}")
    return True


def check_filesystem(device_path: str) -> Optional[str]:
    """
    Check if device has a filesystem and return type

    Args:
        device_path: Device path

    Returns:
        Filesystem type or None
    """
    try:
        result = subprocess.run(
            ['blkid', '-o', 'value', '-s', 'TYPE', device_path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"Error checking filesystem on {device_path}: {e}")

    return None

"""
Filesystem resize operations
"""
import subprocess
import logging
from ..constants import FS_TYPE_EXT4, FS_TYPE_XFS


logger = logging.getLogger(__name__)


def resize_filesystem(device_path: str, mount_path: str, fstype: str) -> bool:
    """
    Resize filesystem to use all available space

    Args:
        device_path: Device path
        mount_path: Mount path (required for XFS)
        fstype: Filesystem type

    Returns:
        True if successful

    Raises:
        Exception: If resize fails
    """
    logger.info(f"Resizing {fstype} filesystem on {device_path}")

    if fstype == FS_TYPE_EXT4:
        cmd = ['resize2fs', device_path]
    elif fstype == FS_TYPE_XFS:
        cmd = ['xfs_growfs', mount_path]
    else:
        raise ValueError(f"Unsupported filesystem type for resize: {fstype}")

    logger.debug(f"Resize command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to resize filesystem: {result.stderr}")

    logger.info(f"Filesystem resized successfully")
    return True


def get_filesystem_type(device_path: str) -> str:
    """
    Get filesystem type from device

    Args:
        device_path: Device path

    Returns:
        Filesystem type

    Raises:
        Exception: If filesystem type cannot be determined
    """
    result = subprocess.run(
        ['blkid', '-o', 'value', '-s', 'TYPE', device_path],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        fstype = result.stdout.strip()
        if fstype:
            return fstype

    raise Exception(f"Cannot determine filesystem type for {device_path}")

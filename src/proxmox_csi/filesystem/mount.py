"""
Mount/unmount operations
"""
import os
import subprocess
import logging
from typing import Optional, List


logger = logging.getLogger(__name__)


def mount_device(device_path: str, target_path: str, fstype: str = 'ext4',
                options: Optional[List[str]] = None) -> bool:
    """
    Mount device to target path

    Args:
        device_path: Device path
        target_path: Mount target path
        fstype: Filesystem type
        options: Mount options

    Returns:
        True if successful

    Raises:
        Exception: If mount fails
    """
    logger.info(f"Mounting {device_path} to {target_path} as {fstype}")

    # Create target directory if not exists
    os.makedirs(target_path, exist_ok=True)

    # Build mount command
    cmd = ['mount']
    if fstype:
        cmd.extend(['-t', fstype])
    if options:
        cmd.extend(['-o', ','.join(options)])
    cmd.extend([device_path, target_path])

    logger.debug(f"Mount command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to mount {device_path}: {result.stderr}")

    logger.info(f"Device {device_path} mounted successfully")
    return True


def unmount_path(target_path: str) -> bool:
    """
    Unmount target path

    Args:
        target_path: Path to unmount

    Returns:
        True if successful

    Raises:
        Exception: If unmount fails
    """
    logger.info(f"Unmounting {target_path}")

    # Run fstrim before unmount (ignore errors)
    try:
        subprocess.run(['fstrim', '-v', target_path],
                      capture_output=True, check=False, timeout=30)
    except Exception as e:
        logger.debug(f"fstrim failed (ignored): {e}")

    # Unmount
    result = subprocess.run(['umount', target_path],
                           capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to unmount {target_path}: {result.stderr}")

    logger.info(f"Path {target_path} unmounted successfully")
    return True


def bind_mount(source_path: str, target_path: str, readonly: bool = False) -> bool:
    """
    Create bind mount from source to target

    Args:
        source_path: Source path
        target_path: Target path
        readonly: Mount as read-only

    Returns:
        True if successful

    Raises:
        Exception: If bind mount fails
    """
    logger.info(f"Bind mounting {source_path} to {target_path} (ro={readonly})")

    # Create target directory/file
    if os.path.isfile(source_path):
        # For raw block, create file
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        if not os.path.exists(target_path):
            open(target_path, 'a').close()
    else:
        os.makedirs(target_path, exist_ok=True)

    options = ['bind']
    if readonly:
        options.append('ro')

    cmd = ['mount', '-o', ','.join(options), source_path, target_path]

    logger.debug(f"Bind mount command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to bind mount: {result.stderr}")

    logger.info(f"Bind mount created successfully")
    return True


def is_mounted(path: str) -> bool:
    """
    Check if path is mounted

    Args:
        path: Path to check

    Returns:
        True if mounted
    """
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                if path in line:
                    return True
    except:
        pass

    return False

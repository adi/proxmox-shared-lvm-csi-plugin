"""
Helper utilities
"""
import time
import logging
from typing import Callable, TypeVar, Any
from functools import wraps


logger = logging.getLogger(__name__)

T = TypeVar('T')


def bytes_to_gib(size_bytes: int) -> float:
    """
    Convert bytes to GiB

    Args:
        size_bytes: Size in bytes

    Returns:
        Size in GiB
    """
    return size_bytes / (1024 ** 3)


def gib_to_bytes(size_gib: float) -> int:
    """
    Convert GiB to bytes

    Args:
        size_gib: Size in GiB

    Returns:
        Size in bytes
    """
    return int(size_gib * (1024 ** 3))


def parse_size_string(size_str: str) -> int:
    """
    Parse size string to bytes

    Args:
        size_str: Size string (e.g., "10G", "512M", "1T")

    Returns:
        Size in bytes

    Raises:
        ValueError: If size format is invalid
    """
    size_str = size_str.strip().upper()

    units = {
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
    }

    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                value = float(size_str[:-1])
                return int(value * multiplier)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")

    # Try to parse as plain bytes
    try:
        return int(size_str)
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}")


def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable string

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    size = float(size_bytes)
    unit_idx = 0

    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1

    return f"{size:.2f} {units[unit_idx]}"


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to retry function on error

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts (seconds)
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts")

            raise last_exception

        return wrapper
    return decorator


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    """
    Safely convert value to string

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        String value or default
    """
    try:
        return str(value) if value is not None else default
    except Exception:
        return default


def ensure_trailing_slash(path: str) -> str:
    """
    Ensure path has trailing slash

    Args:
        path: Path string

    Returns:
        Path with trailing slash
    """
    return path if path.endswith('/') else f"{path}/"


def remove_trailing_slash(path: str) -> str:
    """
    Remove trailing slash from path

    Args:
        path: Path string

    Returns:
        Path without trailing slash
    """
    return path.rstrip('/')

"""Small cross-platform file primitives. No shell, network or GUI dependencies."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile


from .locations import default_home


def shared(path: Path) -> bool:
    return os.getenv('STICKY_INTENT_SHARED')=='1' and path.absolute().is_relative_to(default_home().absolute())


def private_dir(path: Path) -> Path:
    existed=path.exists()
    path.mkdir(parents=True, exist_ok=True, mode=0o770 if shared(path) else 0o700)
    if not existed and shared(path) and os.name!='nt':
        os.chmod(path,(path.stat().st_mode & 0o7777) | 0o070)
    return path


def atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    mode=(0o660 if shared(path) else 0o600) if mode is None else mode
    private_dir(path.parent)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temp = Path(name)
    try:
        if os.name != 'nt':
            os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as f:
            fd = -1
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        if os.name != 'nt':
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if fd != -1:
            os.close(fd)
        temp.unlink(missing_ok=True)


class FileLock:
    """Kernel-managed ownership: crashes release the lock on all supported OSes."""
    def __init__(self, path: Path):
        self.path = path
        self.file = None

    def acquire(self, *, blocking=True) -> bool:
        private_dir(self.path.parent)
        mode=0o660 if shared(self.path) else 0o600
        try:
            fd=os.open(self.path,os.O_RDWR | os.O_CREAT | os.O_EXCL,mode)
            if os.name!='nt': os.fchmod(fd,mode)
        except FileExistsError:
            fd=os.open(self.path,os.O_RDWR)
        self.file = os.fdopen(fd, 'r+b', buffering=0)
        try:
            if os.name == 'nt':
                import msvcrt
                if self.file.seek(0, os.SEEK_END) == 0:
                    self.file.write(b'\0')
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            return True
        except (BlockingIOError, OSError):
            self.file.close()
            self.file = None
            if blocking:
                raise
            return False

    def release(self) -> None:
        if self.file is None:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

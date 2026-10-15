"""Raise an existing widget with only os + the native lock module.

A raise is an ephemeral hint, not durable note data. Atomic replacement keeps
polling race-safe; fsync is deliberately reserved for stored notes and state.
"""
import os


def raise_existing(home):
    try:
        fd = os.open(home / 'widget.lock', os.O_RDWR)
    except FileNotFoundError:
        return False
    locked = False
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (BlockingIOError, OSError) as exc:
            # Do not misclassify an unrelated lock error as a live widget.
            if not isinstance(exc, BlockingIOError) and not (os.name == 'nt' and exc.errno == 13):
                raise
        if locked:
            return False
        token = os.urandom(16).hex().encode()
        temp = home / ('.widget-raise.' + token.decode())
        mode = 0o660 if os.getenv('STICKY_INTENT_SHARED') == '1' else 0o600
        output = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            try:
                if os.name != 'nt':
                    os.fchmod(output, mode)
                offset = 0
                while offset < len(token):
                    written = os.write(output, token[offset:])
                    if not written:
                        raise OSError('Empty write while requesting a widget raise')
                    offset += written
            finally:
                os.close(output)
            os.replace(temp, home / 'widget-raise')
        finally:
            try:
                os.unlink(temp)
            except FileNotFoundError:
                pass
        return True
    finally:
        # Closing releases this probe's lock; never change the owner's lock inode.
        os.close(fd)

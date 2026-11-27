"""刷新报告时保留文件系统实际换出的版本，供并发修改时恢复。"""

import ctypes
import errno
import os
import sys


def replace_with_backup(source, target, backup):
    """发布 source 并返回同一次替换中取下的 target，两个路径在同一文件系统。"""
    if os.name == "nt":
        replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
        replace.argtypes = [ctypes.c_wchar_p] * 3 + [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        if not replace(str(target), str(source), str(backup), 0, None, None):
            error = ctypes.WinError(ctypes.get_last_error())
            if backup.is_file() and not target.exists():
                try:
                    os.link(backup, target)
                except FileExistsError:
                    pass
            raise error
        return backup

    libc = ctypes.CDLL(None, use_errno=True)
    old, new = os.fsencode(source), os.fsencode(target)
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        # RENAME_SWAP exchanges both names in a single filesystem operation.
        result = libc.renamex_np(old, new, 2)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        # AT_FDCWD, RENAME_EXCHANGE
        result = libc.renameat2(-100, old, -100, new, 2)
    else:
        raise OSError(errno.ENOTSUP, "文件系统缺少可保留原件的替换操作")
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))
    return source


def matches(path, content):
    return not path.is_symlink() and path.is_file() and path.read_bytes() == content


def refresh_managed(staged, target, before, content):
    previous = replace_with_backup(staged, target, staged.with_name("previous.md"))
    if matches(previous, before):
        previous.unlink()
        return True
    # A maintainer saved after the last read. Restore that exact file. If
    # another save overlaps the restoration, retain both versions.
    if not matches(target, content):
        raise OSError(f"报告再次变化，另一个版本保留在 {previous}")
    displaced = replace_with_backup(previous, target, staged.with_name("during-restore.md"))
    if not matches(displaced, content):
        raise OSError(f"已恢复先前的人工版本，复原时收到的版本保留在 {displaced}")
    displaced.unlink()
    return False

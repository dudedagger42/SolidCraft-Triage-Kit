"""Extract a downloaded SolidCraft release archive (.zip, .tar.gz) into an EMPTY folder, refusing unsafe entries.

    python -I kit/safe_extract.py <archive> <empty-dir>

Used by kit/getbuild.sh and kit/getbuild.ps1. The archive is untrusted: always run this with -I, and never from inside
the download folder.
"""
import os
import stat
import sys
import tarfile
import zipfile


def bad(name):
    n = name.replace("\\", "/")
    return not n or n.startswith("/") or (len(n) > 1 and n[1] == ":") or ".." in n.split("/")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    archive, dest = sys.argv[1], sys.argv[2]
    if not os.path.isdir(dest) or os.listdir(dest):
        sys.exit(f"safe_extract: {dest} must be an existing empty folder")
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            unsafe = [i.filename for i in infos if bad(i.filename) or stat.S_ISLNK(i.external_attr >> 16)]
            if unsafe:
                sys.exit(f"safe_extract: refused, unsafe entries: {unsafe[:3]}")
            z.extractall(dest)
            for i in infos:  # zipfile drops unix mode bits; keep the executable bit, nothing else
                mode = (i.external_attr >> 16) & 0o777
                if mode & 0o111 and not i.is_dir():
                    p = os.path.join(dest, i.filename)
                    os.chmod(p, os.stat(p).st_mode | 0o755)
    elif archive.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar")):
        with tarfile.open(archive) as t:
            members = t.getmembers()
            # a relative symlink may climb inside the tree (bin/x -> ../lib/x); the data filter refuses any that leave it
            unsafe = [m.name for m in members if bad(m.name) or (m.islnk() and bad(m.linkname))
                      or (m.issym() and m.linkname.replace("\\", "/").startswith("/")) or m.isdev() or m.isfifo()]
            if unsafe:
                sys.exit(f"safe_extract: refused, unsafe entries: {unsafe[:3]}")
            if not hasattr(tarfile, "data_filter"):
                sys.exit("safe_extract: this Python has no tarfile data filter (needs 3.11.4+)")
            t.extractall(dest, filter="data")
    else:
        sys.exit(f"safe_extract: unknown archive type: {os.path.basename(archive)}")
    print(f"safe_extract: {len(os.listdir(dest))} top-level entr(y/ies) in {dest}")


if __name__ == "__main__":
    main()

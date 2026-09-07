import ftplib
from pathlib import Path


class MissingRemoteFile(Exception):
    pass


class FTPSourceClient:
    def __init__(self, host: str, user: str, password: str, timeout: int = 60):
        self.host = host
        self.user = user
        self.password = password
        self.timeout = timeout
        self.ftp: ftplib.FTP | None = None

    def __enter__(self):
        self._connect()
        return self

    def _connect(self) -> None:
        self.ftp = ftplib.FTP(timeout=self.timeout)
        self.ftp.connect(self.host)
        self.ftp.login(self.user, self.password)
        self.ftp.encoding = "utf-8"

    def _ensure_connection(self) -> None:
        if not self.ftp:
            self._connect()
            return
        try:
            self.ftp.voidcmd("NOOP")
        except ftplib.all_errors:
            try:
                self.ftp.close()
            finally:
                self.ftp = None
            self._connect()

    def download(self, remote_name: str, destination: Path) -> Path:
        self._ensure_connection()
        part = destination.with_name(destination.name + ".part")
        try:
            with part.open("wb") as output:
                self.ftp.retrbinary(f"RETR {remote_name}", output.write)
            part.replace(destination)
        except ftplib.error_perm as exc:
            part.unlink(missing_ok=True)
            if str(exc).startswith("550"):
                raise MissingRemoteFile(remote_name) from exc
            raise
        except Exception:
            part.unlink(missing_ok=True)
            raise
        return destination

    def __exit__(self, exc_type, exc, traceback):
        if self.ftp:
            try:
                self.ftp.quit()
            except ftplib.all_errors:
                self.ftp.close()

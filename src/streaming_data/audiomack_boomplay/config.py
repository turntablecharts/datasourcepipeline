from dataclasses import dataclass
from pathlib import Path

from src.utils.constant import EnvConstants


@dataclass(frozen=True)
class StreamingConfig:
    ftp_host: str | None = EnvConstants.FTP_HOST
    ftp_user: str | None = EnvConstants.FTP_USER
    ftp_password: str | None = EnvConstants.FTP_PASS
    gpg_passphrase: str | None = EnvConstants.GPG_PASSPHRASE
    gpg_binary: str = EnvConstants.GPG_BINARY
    timezone: str = EnvConstants.STREAMING_TIMEZONE
    staging_dir: Path | None = (
        Path(EnvConstants.STREAMING_STAGING_DIR)
        if EnvConstants.STREAMING_STAGING_DIR
        else None
    )
    slack_webhook_url: str | None = EnvConstants.SLACK_WEBHOOK_URL

    def validate_ingestion(self) -> None:
        missing = [
            name for name, value in (
                ("FTP_HOST", self.ftp_host),
                ("FTP_USER", self.ftp_user),
                ("FTP_PASS", self.ftp_password),
                ("GPG_PASSPHRASE", self.gpg_passphrase),
            ) if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required ingestion configuration: {', '.join(missing)}")

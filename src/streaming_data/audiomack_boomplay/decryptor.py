from pathlib import Path

import gnupg


def decrypt_audiomack(source: Path, destination: Path, passphrase: str, gpg_binary: str) -> Path:
    gpg = gnupg.GPG(binary=gpg_binary)
    with source.open("rb") as encrypted:
        result = gpg.decrypt_file(encrypted, passphrase=passphrase)
    if not result.ok:
        raise RuntimeError(f"Could not decrypt {source.name}: {result.status or 'unknown GPG error'}")
    destination.write_bytes(result.data)
    return destination

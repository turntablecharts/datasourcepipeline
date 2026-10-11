from pathlib import Path
import subprocess


DECRYPT_TIMEOUT_SECONDS = 300


def decrypt_audiomack(source: Path, destination: Path, passphrase: str, gpg_binary: str) -> Path:
    """Decrypt to disk without interactive prompts or an unbounded GPG wait."""
    if "\n" in passphrase or "\r" in passphrase:
        raise ValueError("GPG passphrase must not contain a newline")
    try:
        result = subprocess.run(
            [gpg_binary, "--batch", "--yes", "--no-tty",
             "--pinentry-mode", "loopback", "--passphrase-fd", "0",
             "--output", str(destination), "--decrypt", str(source)],
            input=(passphrase + "\n").encode(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DECRYPT_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Could not decrypt {source.name}: GPG exited with code {result.returncode}")
        if not destination.is_file():
            raise RuntimeError(f"Could not decrypt {source.name}: GPG produced no output file")
    except subprocess.TimeoutExpired:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not decrypt {source.name}: GPG exceeded {DECRYPT_TIMEOUT_SECONDS} seconds"
        ) from None
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination

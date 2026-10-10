"""Install verified Swiss data files while building the container."""
from pathlib import Path
import hashlib
from urllib.request import urlopen

SOURCE_COMMIT = "aacf962d19d79f8bc921dbcdaacf306d85be1917"
FILES = {
    "sepl_18.se1": "ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66",
    "semo_18.se1": "1ca07bd67c24374d77226180c20a4f9996cba013697894810518e7eb582ca4f7",
}


def prepare():
    directory = Path(__file__).resolve().parent / "ephe"
    directory.mkdir(exist_ok=True)
    for name, expected_hash in FILES.items():
        target = directory / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected_hash:
            continue
        url = f"https://raw.githubusercontent.com/aloistr/swisseph/{SOURCE_COMMIT}/ephe/{name}"
        with urlopen(url, timeout=60) as response:
            data = response.read(2_000_000)
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise RuntimeError(f"Swiss ephemeris checksum mismatch: {name}")
        target.write_bytes(data)
        print(f"Verified Swiss ephemeris data: {name}")


if __name__ == "__main__":
    prepare()

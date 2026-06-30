"""Hash a PIN with bcrypt for secrets.toml.

Usage:
    python3 scripts/hash_pin.py 1234
"""

from __future__ import annotations

import sys

import bcrypt


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 scripts/hash_pin.py <PIN>")
    pin = sys.argv[1].encode()
    print(bcrypt.hashpw(pin, bcrypt.gensalt()).decode())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
gen_password.py — generate N random 8-char passwords satisfying complexity rules.

Usage:
    python3 gen_password.py <N>

Output:
    N space-separated passwords on a single stdout line.

Complexity per password (8 chars):
    - At least 1 lowercase letter  [a-z]
    - At least 1 uppercase letter  [A-Z]
    - At least 1 digit             [0-9]
    - At least 1 special character [!@#$%^&*]
    - Remaining chars drawn from all of the above pools
"""

import secrets
import string
import sys


LOWER   = string.ascii_lowercase          # a-z
UPPER   = string.ascii_uppercase          # A-Z
DIGITS  = string.digits                   # 0-9
SPECIAL = "!@#$%^&*"
ALL     = LOWER + UPPER + DIGITS + SPECIAL
LENGTH  = 8


def gen_one() -> str:
    """Return a single password guaranteed to meet all complexity rules."""
    while True:
        # Guarantee one char from each required class
        mandatory = [
            secrets.choice(LOWER),
            secrets.choice(UPPER),
            secrets.choice(DIGITS),
            secrets.choice(SPECIAL),
        ]
        # Fill remaining positions from the full pool
        rest = [secrets.choice(ALL) for _ in range(LENGTH - len(mandatory))]
        chars = mandatory + rest
        secrets.SystemRandom().shuffle(chars)
        pw = "".join(chars)

        # Double-check (should always pass, but be explicit)
        if (any(c in LOWER   for c in pw) and
            any(c in UPPER   for c in pw) and
            any(c in DIGITS  for c in pw) and
            any(c in SPECIAL for c in pw)):
            return pw


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <count>", file=sys.stderr)
        sys.exit(1)

    try:
        n = int(sys.argv[1])
        if n < 1:
            raise ValueError
    except ValueError:
        print(f"Error: <count> must be a positive integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    passwords = [gen_one() for _ in range(n)]
    print(" ".join(passwords))


if __name__ == "__main__":
    main()

#!/bin/sh
set -eu
mkdir -p /logs/verifier
# A failed verifier must never leave a success reward or omit the reward file.
printf '0\n' > /logs/verifier/reward.txt
exec python3 /tests/verify.py

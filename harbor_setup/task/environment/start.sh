#!/bin/sh
set -eu
# Runs before Harbor uploads the oracle's script. Real agents never receive it.
test ! -e /tests
test ! -e /solution
mkdir -p /logs/artifacts
printf '%s\n' '{"purpose":"infrastructure-preparation-only","tests_absent_at_start":true,"solution_absent_at_start":true}' > /logs/artifacts/environment-start.json
exec "$@"

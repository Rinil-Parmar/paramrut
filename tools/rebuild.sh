#!/usr/bin/env bash
# Rebuild data/ and text/ from the APK. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
[ -d apk ] || unzip -q -o paramrut-5.1.apk -x 'classes*.dex' 'lib/*' -d apk
python3 extract.py "$@"

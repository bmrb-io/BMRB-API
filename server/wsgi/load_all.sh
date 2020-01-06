#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
${DIR}/setup_virtualenv.sh
source ${DIR}/virtual_env/bin/activate || exit 1
cd ${DIR} || exit 2
python3 -m bmrbapi.reloaders "$@"

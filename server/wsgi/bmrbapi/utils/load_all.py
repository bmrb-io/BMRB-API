#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
source ${DIR}/../../virtual_env/bin/activate

cd ${DIR}/../.. || exit 1
python3 -m bmrbapi.reloaders "$@"

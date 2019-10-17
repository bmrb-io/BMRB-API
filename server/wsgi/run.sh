#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
"${SCRIPT_DIR}"/setup_virtualenv.sh
source "${SCRIPT_DIR}"/virtual_env/bin/activate
cd "${SCRIPT_DIR}" || exit 1
export FLASK_APP=bmrbapi
export FLASK_DEBUG=1
python3 -m flask run --host=0.0.0.0 --port 9000

#!/bin/bash

python -m virtualenv env
source env/bin/activate
pip install -r ../configs/requirements.txt
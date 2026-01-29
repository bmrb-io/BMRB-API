#!/bin/bash
set -e

# Create symlinks from expected binary locations to the pre-built binaries
# This allows the wsgi code to be mounted as a volume while still using compiled binaries

# Ensure the target directories exist
mkdir -p /opt/wsgi/bmrbapi/reloaders
mkdir -p /opt/wsgi/bmrbapi/submodules

# Create symlinks for the compiled binaries
ln -sfn /opt/binaries/molprobity_binary /opt/wsgi/bmrbapi/reloaders/molprobity_binary
ln -sfn /opt/binaries/fasta36 /opt/wsgi/bmrbapi/submodules/fasta36

# Execute the main command
exec "$@"

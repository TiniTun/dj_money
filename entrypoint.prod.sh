#!/bin/sh

# This script is executed as root.

# Set ownership of the shared volume so that the 'app' user can write to it.
# This is necessary because Docker mounts named volumes as root.
chown -R app:app /home/app/web/tmp

# Drop privileges and execute the main command (passed as arguments to this script)
# as the non-root 'app' user.
exec gosu app "$@"
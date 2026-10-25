#!/bin/sh

# This script is executed as root.

# Set ownership of the shared volumes so that the 'app' user can write to them.
# This is necessary because Docker mounts named volumes as root.
mkdir -p /home/app/web/tmp /home/app/web/static /home/app/web/media /home/app/web/frontend_public
chown -R app:app /home/app/web/tmp /home/app/web/static /home/app/web/media /home/app/web/frontend_public

# Drop privileges and execute the main command (passed as arguments to this script)
# as the non-root 'app' user.
exec gosu app "$@"
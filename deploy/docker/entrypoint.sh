#!/bin/sh
# Container entry point: create the state folders on the /state volume, then start the bot.
set -e
mkdir -p /state/logs /state/actjobs/data /state/actjobs/reports /state/actjobs/logs
exec fgbot "$@"

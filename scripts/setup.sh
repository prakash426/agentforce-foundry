#!/bin/sh
set -e
sf org create scratch -f config/project-scratch-def.json -a foundry -d 7
sf project deploy start -o foundry
sf apex run test -o foundry

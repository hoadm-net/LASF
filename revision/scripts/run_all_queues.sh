#!/bin/bash
# Start the three run queues together; queue 2 and 3 wait for the previous one to finish.
# Completed steps are skipped, so this is safe to re-run after a restart.
cd "$(dirname "$0")/../.." || exit 1
echo "$(date '+%F %T') START all queues" >> logs/queue.log
./revision/scripts/run_queue.sh &
./revision/scripts/run_queue2.sh &
./revision/scripts/run_queue3.sh &
wait

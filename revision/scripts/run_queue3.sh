#!/bin/bash
# Third queue (E9): sample values capped at 50 characters in augmented prompts, ViBIRD.
cd "$(dirname "$0")/../.." || exit 1
source /venv/main/bin/activate
export HF_HUB_OFFLINE=1
LOG=logs/queue.log
DETAIL=logs/queue_detail.log
until grep -q "QUEUE2 FINISHED" $LOG; do sleep 60; done
for m in Qwen/Qwen2.5-Coder-0.5B-Instruct Qwen/Qwen2.5-Coder-1.5B-Instruct Qwen/Qwen2.5-Coder-3B-Instruct Qwen/Qwen2.5-Coder-7B-Instruct; do
    for c in +aug full; do
        tag=$(echo $c | sed 's/+/plus/')_$(basename $m | tr 'A-Z' 'a-z' | sed 's/-instruct//')_v50
        [ -f evaluation/results_v2/bird_vi/$tag.jsonl ] && continue
        echo "$(date '+%F %T') START e9_$tag" | tee -a $LOG
        if python run_experiment.py --dataset bird_vi --model $m --config $c --max_value_chars 50 \
            --batch-size 4 --max_batch_tokens 32768 >> $DETAIL 2>&1; then
            echo "$(date '+%F %T') DONE  e9_$tag" | tee -a $LOG
        else
            echo "$(date '+%F %T') FAIL  e9_$tag" | tee -a $LOG
        fi
    done
done
echo "$(date '+%F %T') QUEUE3 FINISHED" | tee -a $LOG

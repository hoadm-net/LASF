#!/bin/bash
# Fourth queue (E10): `full` with zero-shot LLM table selection instead of e5 column retrieval.
# Selected tables keep all their columns; the prompt carries the Vietnamese metadata.
# Table selections are read from the E7 cache (evaluation/analysis_v2/llm_selection/).
# Last step: ViBIRD with sample values capped at 50 characters (as in E9).
cd "$(dirname "$0")/../.." || exit 1
source /venv/main/bin/activate
export HF_HUB_OFFLINE=1
LOG=logs/queue.log
DETAIL=logs/queue_detail.log

step() {  # step <name> <command...>
    local name=$1; shift
    echo "$(date '+%F %T') START $name" | tee -a $LOG
    if "$@" >> $DETAIL 2>&1; then
        echo "$(date '+%F %T') DONE  $name" | tee -a $LOG
    else
        echo "$(date '+%F %T') FAIL  $name (exit $?)" | tee -a $LOG
    fi
}

for d in spider_vi bird_vi; do
    step e10_full_llm_$d python scripts/run_ablation.py --dataset $d --configs full --linker llm --skip_reference
done
for m in Qwen/Qwen2.5-Coder-0.5B-Instruct Qwen/Qwen2.5-Coder-1.5B-Instruct Qwen/Qwen2.5-Coder-3B-Instruct Qwen/Qwen2.5-Coder-7B-Instruct; do
    tag=full_llm_$(basename $m | tr 'A-Z' 'a-z' | sed 's/-instruct//')_v50
    [ -f evaluation/results_v2/bird_vi/$tag.jsonl ] && continue
    step e10_$tag python run_experiment.py --dataset bird_vi --model $m --config full --linker llm \
        --max_value_chars 50 --batch-size 4 --max_batch_tokens 32768
done
echo "$(date '+%F %T') QUEUE4 FINISHED" | tee -a $LOG

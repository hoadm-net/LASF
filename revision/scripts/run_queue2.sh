#!/bin/bash
# Second queue: baselines (E7) and latency benchmark (E8). Starts after run_queue.sh finishes.
# Restartable: run_ablation skips existing outputs.

cd "$(dirname "$0")/../.." || exit 1
source /venv/main/bin/activate
export HF_HUB_OFFLINE=1
LOG=logs/queue.log
DETAIL=logs/queue_detail.log

until grep -q "QUEUE FINISHED" $LOG; do sleep 60; done

step() {
    local name=$1; shift
    echo "$(date '+%F %T') START $name" | tee -a $LOG
    if "$@" >> $DETAIL 2>&1; then
        echo "$(date '+%F %T') DONE  $name" | tee -a $LOG
    else
        echo "$(date '+%F %T') FAIL  $name (exit $?)" | tee -a $LOG
    fi
}

# --- E7: existing-style schema-filtering baselines, plain prompt ---
for d in spider_vi bird_vi; do
    [ -f evaluation/analysis_v2/llm_selection/$d.jsonl ] || step e7_llmsel_$d python scripts/llm_table_selection.py --dataset $d
    [ -f evaluation/analysis_v2/recall_baselines/${d}_summary.csv ] || step e7_recall_$d python scripts/retrieval_recall.py --dataset $d --linkers bm25-plain bm25-aug llm-select \
        --out evaluation/analysis_v2/recall_baselines
    step e7_bm25_$d python scripts/run_ablation.py --dataset $d --configs augret --linker bm25 --skip_reference
    step e7_llm_$d python scripts/run_ablation.py --dataset $d --configs +link --linker llm --skip_reference
done

# --- E8: latency / memory, batch size 1, 200 sampled questions per dataset ---
for d in spider_vi bird_vi; do
    for m in Qwen/Qwen2.5-Coder-0.5B-Instruct Qwen/Qwen2.5-Coder-1.5B-Instruct Qwen/Qwen2.5-Coder-3B-Instruct Qwen/Qwen2.5-Coder-7B-Instruct; do
        for c in baseline full; do
            out=evaluation/analysis_v2/latency/$d/${c}_$(basename $m | tr 'A-Z' 'a-z' | sed 's/-instruct//')_sample200.jsonl
            [ -f "$out" ] && continue
            step e8_${d}_${c}_$(basename $m) python run_experiment.py --dataset $d --model $m --config $c \
                --sample 200 --batch-size 1 --results_dir evaluation/analysis_v2/latency
        done
    done
done

echo "$(date '+%F %T') QUEUE2 FINISHED" | tee -a $LOG

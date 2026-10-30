#!/bin/bash
# Run the revision experiments in plan order (revision/EXPERIMENT_PLAN.md).
# Every step skips outputs that already exist, so the queue can be restarted at any time.
# Progress: logs/queue.log (one line per step) and logs/queue_detail.log (full output).

cd "$(dirname "$0")/../.." || exit 1
source /venv/main/bin/activate
export HF_HUB_OFFLINE=1
mkdir -p logs
LOG=logs/queue.log
DETAIL=logs/queue_detail.log

step() {  # step <name> <command...>
    local name=$1; shift
    echo "$(date '+%F %T') START $name" | tee -a $LOG
    if "$@" >> $DETAIL 2>&1; then
        echo "$(date '+%F %T') DONE  $name" | tee -a $LOG
    else
        echo "$(date '+%F %T') FAIL  $name (exit $?)" | tee -a $LOG
        return 1
    fi
}

M05=Qwen/Qwen2.5-Coder-0.5B-Instruct
M15=Qwen/Qwen2.5-Coder-1.5B-Instruct
M7=Qwen/Qwen2.5-Coder-7B-Instruct

# --- B1: augmentation (required by everything below) ---
step aug_spider python augmentation/generate_aug.py --dataset spider_vi --device cuda || exit 1
step aug_bird python augmentation/generate_aug.py --dataset bird_vi --device cuda || exit 1
step aug_check python revision/scripts/check_augmentation.py || exit 1

# --- E4: recall with and without augmentation ---
[ -f evaluation/analysis_v2/recall/spider_vi_summary.csv ] || step e4_recall_spider python scripts/retrieval_recall.py --dataset spider_vi --linkers e5-plain e5-aug
[ -f evaluation/analysis_v2/recall/bird_vi_summary.csv ] || step e4_recall_bird python scripts/retrieval_recall.py --dataset bird_vi --linkers e5-plain e5-aug

# Smoke tests on the longest prompts (european_football_2, 7B, --limit 8) passed on 2026-10-29
# and are no longer repeated on restart.

# --- E1: ViSpider (Vietnamese questions), 4 models x 5 configs + GPT-4.1-mini baseline/full ---
step e1_spider python scripts/run_ablation.py --dataset spider_vi

# --- E2: ViBIRD, pipeline v2 ---
step e2_bird python scripts/run_ablation.py --dataset bird_vi

# --- E3: English questions (cross-lingual gap) ---
step e3_spider_en python scripts/run_ablation.py --dataset spider_vi --lang en --configs baseline full --skip_reference
step e3_bird_en python scripts/run_ablation.py --dataset bird_vi --lang en --configs baseline full --skip_reference

# --- E5: k sensitivity ---
for k in 20 30 50; do
    for m in $M15 $M7; do
        step e5_bird_k${k}_$(basename $m) python scripts/run_ablation.py --dataset bird_vi --model $m \
            --configs +link full --top_k $k --skip_reference
    done
done
for k in 5 20; do
    for m in $M15 $M7; do
        step e5_spider_k${k}_$(basename $m) python scripts/run_ablation.py --dataset spider_vi --model $m \
            --configs full --top_k $k --skip_reference
    done
done

echo "$(date '+%F %T') QUEUE FINISHED" | tee -a $LOG

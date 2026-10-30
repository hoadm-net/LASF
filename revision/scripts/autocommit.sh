#!/bin/bash
# Commit and push finished experiment outputs every 10 minutes.
# A run counts as finished once its .meta.json exists; an analysis output once its
# summary/meta file is newer than the per-question file.
cd "$(dirname "$0")/../.." || exit 1

finished() {
    for meta in evaluation/results_v2/*/*.meta.json evaluation/analysis_v2/*/*.meta.json \
                evaluation/analysis_v2/latency/*/*.meta.json; do
        [ -f "$meta" ] || continue
        case "$meta" in *limit8*) continue ;; esac
        echo "$meta"
        [ -f "${meta%.meta.json}.jsonl" ] && echo "${meta%.meta.json}.jsonl"
    done
    for summary in evaluation/analysis_v2/*/*_summary.csv; do
        per_q="${summary%_summary.csv}_per_question.jsonl"
        if [ -f "$per_q" ] && ! [ "$summary" -nt "$per_q" ]; then continue; fi  # still being written
        echo "$summary"
        [ -f "$per_q" ] && echo "$per_q"
    done
}

while true; do
    git add $(finished) 2>/dev/null
    if ! git diff --cached --quiet; then
        new=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.meta\.json$|_summary\.csv$' \
              | xargs -n1 basename | sed -E 's/\.meta\.json$|_summary\.csv$//' | sort -u | paste -sd, -)
        git -c user.name="Hòa Đinh" commit -q -m "Add results: ${new:-updated outputs}"
    fi
    if [ -n "$(git log origin/revision-jict..HEAD 2>/dev/null)" ]; then
        git push -q origin revision-jict && echo "$(date '+%F %T') pushed $(git log -1 --format=%h)"
    fi
    sleep 600
done

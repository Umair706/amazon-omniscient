#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_analyses.sh — Run 10 niche analyses sequentially against the Omniscient API
#
# Usage:
#   ./run_analyses.sh              # defaults: AU marketplace, http://localhost:8000
#   ./run_analyses.sh US           # override marketplace
#   BACKEND_URL=http://myhost:8000 ./run_analyses.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MARKETPLACE="${1:-AU}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
API="${BACKEND_URL}/api/v1"
POLL_INTERVAL=10   # seconds between status polls

# 10 diverse product-research keywords across different categories
KEYWORDS=(
  "baby silicone bibs"
  "resistance bands set"
  "stainless steel water bottle"
  "wireless earbuds case"
  "yoga mat thick"
  "silicone kitchen utensils set"
  "led desk lamp"
  "dog poop bag dispenser"
  "reusable produce bags"
  "car phone mount magnetic"
)

# ── Helpers ──────────────────────────────────────────────────────────────────

timestamp() { date "+%H:%M:%S"; }

wait_for_backend() {
  echo "[$(timestamp)] Waiting for backend at ${BACKEND_URL} ..."
  local retries=0
  while ! curl -sf "${API}/health" >/dev/null 2>&1 \
     && ! curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1 \
     && ! curl -sf "${BACKEND_URL}/docs" >/dev/null 2>&1; do
    retries=$((retries + 1))
    if [ "$retries" -ge 30 ]; then
      echo "[$(timestamp)] ERROR: Backend not reachable after 30 attempts. Is the server running?"
      exit 1
    fi
    sleep 2
  done
  echo "[$(timestamp)] Backend is up."
}

submit_analysis() {
  local keyword="$1"
  local response
  response=$(curl -sf -X POST "${API}/jobs/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"keyword\": \"${keyword}\", \"marketplace\": \"${MARKETPLACE}\", \"force\": true}" \
    2>&1) || {
      echo "[$(timestamp)]   ERROR submitting: ${response}"
      return 1
    }

  local job_id
  job_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null) || {
    echo "[$(timestamp)]   ERROR parsing response: ${response}"
    return 1
  }
  local niche_id
  niche_id=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('niche_id','?'))" 2>/dev/null)

  echo "$job_id|$niche_id"
}

poll_until_done() {
  local job_id="$1"
  local keyword="$2"
  local last_step=""
  local last_progress=""

  while true; do
    local response
    response=$(curl -sf "${API}/jobs/${job_id}/status" 2>&1) || {
      echo "[$(timestamp)]   Poll failed, retrying in ${POLL_INTERVAL}s..."
      sleep "$POLL_INTERVAL"
      continue
    }

    local status progress step error
    status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)
    progress=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progress',0) or 0)" 2>/dev/null)
    step=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('step',''))" 2>/dev/null)
    error=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','') or '')" 2>/dev/null)

    # Only print when progress or step changes
    if [[ "$progress" != "$last_progress" || "$step" != "$last_step" ]]; then
      local step_display=""
      [[ -n "$step" ]] && step_display=" | ${step}"
      echo "[$(timestamp)]   ${status} ${progress}%${step_display}"
      last_progress="$progress"
      last_step="$step"
    fi

    case "$status" in
      completed)
        local score tier niche_id rec_id
        score=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('omniscient_score','N/A'))" 2>/dev/null)
        tier=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('confidence_tier','N/A'))" 2>/dev/null)
        niche_id=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('niche_id','?'))" 2>/dev/null)
        rec_id=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result') or {}; print(r.get('recommendation_id','?'))" 2>/dev/null)
        echo "$score|$tier|$niche_id|$rec_id"
        return 0
        ;;
      failed)
        echo "[$(timestamp)]   FAILED: ${error}"
        echo "FAILED|${error}||"
        return 1
        ;;
    esac

    sleep "$POLL_INTERVAL"
  done
}

# ── Main ─────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Omniscient — Batch Analysis Runner"
echo "  Marketplace: ${MARKETPLACE} | API: ${API}"
echo "  Keywords:    ${#KEYWORDS[@]}"
echo "═══════════════════════════════════════════════════════════════════════"

wait_for_backend

declare -a RESULTS=()
passed=0
failed=0
total=${#KEYWORDS[@]}

for i in "${!KEYWORDS[@]}"; do
  keyword="${KEYWORDS[$i]}"
  n=$((i + 1))

  echo ""
  echo "───────────────────────────────────────────────────────────────────────"
  echo "[$(timestamp)] (${n}/${total}) Analyzing: \"${keyword}\""
  echo "───────────────────────────────────────────────────────────────────────"

  # Submit
  submit_result=$(submit_analysis "$keyword") || {
    echo "[$(timestamp)]   Submission failed — skipping."
    RESULTS+=("FAIL|${keyword}|submission_error|||")
    failed=$((failed + 1))
    continue
  }

  job_id=$(echo "$submit_result" | cut -d'|' -f1)
  niche_id=$(echo "$submit_result" | cut -d'|' -f2)
  echo "[$(timestamp)]   Job: ${job_id} | Niche: ${niche_id}"

  # Poll
  start_time=$(date +%s)
  poll_result=$(poll_until_done "$job_id" "$keyword") || true
  end_time=$(date +%s)
  elapsed=$(( end_time - start_time ))

  score=$(echo "$poll_result" | cut -d'|' -f1)
  tier=$(echo "$poll_result" | cut -d'|' -f2)
  final_niche=$(echo "$poll_result" | cut -d'|' -f3)
  rec_id=$(echo "$poll_result" | cut -d'|' -f4)

  if [[ "$score" == "FAILED" ]]; then
    echo "[$(timestamp)]   FAILED after ${elapsed}s"
    RESULTS+=("FAIL|${keyword}|${tier}|||${elapsed}s")
    failed=$((failed + 1))
  else
    echo "[$(timestamp)]   DONE in ${elapsed}s — Score: ${score} (${tier})"
    RESULTS+=("PASS|${keyword}|${score}|${tier}|${rec_id}|${elapsed}s")
    passed=$((passed + 1))
  fi
done

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  RESULTS SUMMARY"
echo "═══════════════════════════════════════════════════════════════════════"
printf "  %-4s  %-35s  %6s  %-9s  %s\n" "#" "Keyword" "Score" "Tier" "Time"
echo "  ────  ───────────────────────────────────  ──────  ─────────  ────────"

for i in "${!RESULTS[@]}"; do
  IFS='|' read -r status keyword score_or_err tier rec_id elapsed <<< "${RESULTS[$i]}"
  n=$((i + 1))
  if [[ "$status" == "PASS" ]]; then
    printf "  %-4s  %-35s  %6s  %-9s  %s\n" "${n}." "${keyword:0:35}" "$score_or_err" "$tier" "$elapsed"
  else
    printf "  %-4s  %-35s  %6s  %-9s  %s\n" "${n}." "${keyword:0:35}" "FAIL" "-" "$elapsed"
  fi
done

echo "  ────  ───────────────────────────────────  ──────  ─────────  ────────"
echo "  Passed: ${passed}/${total}  |  Failed: ${failed}/${total}"
echo "═══════════════════════════════════════════════════════════════════════"

exit $((failed > 0 ? 1 : 0))

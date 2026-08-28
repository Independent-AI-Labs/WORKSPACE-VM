#!/bin/bash
set -euo pipefail

MAX_INPUT_TOKENS=16384
CURL_BIN="curl"
VERSION="${OPENCODE_MODERATOR_VERSION:-unknown}"
CAPTURE_FILE="${OPENCODE_MODERATOR_CAPTURE:?missing moderator capture path}"
CONFIG_FILE="${OPENCODE_MODERATOR_CONFIG:?missing moderator configuration path}"
BASE_URL="$(jq -er '.gateway_url' "$CONFIG_FILE")"
MODEL="$(jq -er '.model' "$CONFIG_FILE")"
[[ "$BASE_URL" == "http://127.0.0.1:9080/llamafile" ]] || {
  printf 'moderator configuration must use the Workspace Gateway relay\n' >&2
  exit 1
}
INPUT_FILE="$(mktemp)"
MESSAGES_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
VALIDATION_FILE="$(mktemp)"
TOKEN_RESPONSE_FILE="$(mktemp)"
TOKEN_PAYLOAD_FILE="$(mktemp)"
trap 'rm -f "$INPUT_FILE" "$MESSAGES_FILE" "$RESPONSE_FILE" "$VALIDATION_FILE" "$TOKEN_RESPONSE_FILE" "$TOKEN_PAYLOAD_FILE"' EXIT

cat >"$INPUT_FILE"

append_yaml_block() {
  local key="$1"
  local file="$2"
  printf '%s: |\n' "$key" >>"$CAPTURE_FILE"
  if [[ -n "$file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      printf '  %s\n' "$line" >>"$CAPTURE_FILE"
    done <"$file"
    return
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    printf '  %s\n' "$line" >>"$CAPTURE_FILE"
  done
}

jq -e '
  .todos and (.messages | type == "array")
' "$INPUT_FILE" >"$VALIDATION_FILE"

jq -c --arg retry_marker '⚠️ Local Moderator Continuation' --arg trace_marker '🔎 Local Moderator Decision' '
  def text:
    [.parts[]? | select(.type == "text") | .text // empty] | join("\n");
  def normalized:
    [.messages | to_entries[] |
      {index: .key, role: .value.info.role, content: (.value | text)} |
      select((.role == "user" or .role == "assistant") and .content != "") |
       select(.role != "user" or ((.content | contains($retry_marker) | not) and (.content | contains($trace_marker) | not)))];
  (normalized) as $all |
  ([$all[] | select(.role == "user")]) as $users |
  ($users | .[-3:]) as $selected |
  (if ($selected | length) == 0 then 0 else $selected[0].index end) as $start |
  {
    todos: .todos,
    transcript: ([{role: "user", content: ("TODO LIST:\n" + (.todos | tojson) + "\n\nTRANSCRIPT:")}]
      + [$all[] | select(.index >= $start) | {role, content}])
  }
' "$INPUT_FILE" >"$MESSAGES_FILE"

build_payload() {
  jq -cn --argjson transcript "$(jq -c '.transcript' "$MESSAGES_FILE")" '
    {
      messages: ([
         {role: "system", content: "MODERATOR_DECISION_YAML_V2. You are MiniCPM, the moderator, not the working agent. Assess the task, todos, user instructions, transcript, and final agent response. Return exactly two YAML lines and nothing else:\ndecision: PASS\nreason: COMPLETE\nDecision is exactly PASS, CONTINUE_PROGRESS, CONTINUE_NO_PROGRESS, or BLOCKED. Reason is exactly COMPLETE, WORK_REMAINS, NO_PROGRESS, EXTERNAL_BLOCKER, or CLARIFICATION_REQUIRED. PASS means all required work is complete. CONTINUE_PROGRESS means substantive work occurred but required work remains. CONTINUE_NO_PROGRESS means the response is only an assertion, repeated status, or no meaningful progress. BLOCKED means a genuine external blocker or clarification is required. [WORK DONE] is not proof. Required pending or in_progress todos make PASS impossible unless the transcript establishes a genuine blocker, clarification request, or intentional deferral of non-required work. Never invent results or output prose, headings, todos, rulings, JSON, or markdown."}
        ] + $transcript + [
          {role: "user", content: "LOOP REVIEW: Emit exactly decision and one approved reason code. Do not let a completion marker or a claim of continuing override the transcript and todos."}
       ])
    }
  '
}

token_count() {
  local payload="$1"
  printf '%s' "$payload" >"$TOKEN_PAYLOAD_FILE"
  if ! "$CURL_BIN" --fail-with-body --no-progress-meter --show-error --max-time 120 \
    -H 'content-type: application/json' \
    --data-binary "@$TOKEN_PAYLOAD_FILE" \
    "${BASE_URL%/}/v1/chat/completions/input_tokens" >"$TOKEN_RESPONSE_FILE"; then
    cat "$TOKEN_RESPONSE_FILE" >&2
    return 1
  fi
  jq -e -r '.input_tokens' "$TOKEN_RESPONSE_FILE"
}

while true; do
  PAYLOAD="$(build_payload)"
  TOKENS="$(token_count "$PAYLOAD")"
  [[ "$TOKENS" =~ ^[0-9]+$ ]] || { printf 'invalid token count: %s\n' "$TOKENS" >&2; exit 1; }
  (( TOKENS <= MAX_INPUT_TOKENS )) && break
  jq -e '
    (.transcript | to_entries | map(select(.value.role == "assistant")) | .[0].key) as $drop |
    if $drop == null then error("mandatory moderator context exceeds 16K tokens")
    else .transcript = ([.transcript | to_entries[] | select(.key != $drop) | .value]) end
  ' "$MESSAGES_FILE" >"$MESSAGES_FILE.tmp"
  mv "$MESSAGES_FILE.tmp" "$MESSAGES_FILE"
done

MODERATOR_GRAMMAR=$'root ::= "decision: PASS\\nreason: COMPLETE" | "decision: CONTINUE_PROGRESS\\nreason: WORK_REMAINS" | "decision: CONTINUE_NO_PROGRESS\\nreason: WORK_REMAINS" | "decision: CONTINUE_NO_PROGRESS\\nreason: NO_PROGRESS" | "decision: BLOCKED\\nreason: EXTERNAL_BLOCKER" | "decision: BLOCKED\\nreason: CLARIFICATION_REQUIRED"'
FINAL_PAYLOAD="$(jq -c --arg model "$MODEL" --arg grammar "$MODERATOR_GRAMMAR" '. + {model: $model, temperature: 0, max_tokens: 128, grammar: $grammar}' "$TOKEN_PAYLOAD_FILE")"
printf '%s' "$FINAL_PAYLOAD" >"$TOKEN_PAYLOAD_FILE"
printf 'version: %s\nsessionID: %s\ntokenCount: %s\n' "$VERSION" "$(jq -r '.session_id' "$INPUT_FILE")" "$TOKENS" >"$CAPTURE_FILE"
printf 'request: |\n' >>"$CAPTURE_FILE"
while IFS= read -r line || [[ -n "$line" ]]; do
  printf '  %s\n' "$line" >>"$CAPTURE_FILE"
done <"$TOKEN_PAYLOAD_FILE"
if ! "$CURL_BIN" --fail-with-body --no-progress-meter --show-error --max-time 300 \
  -H 'content-type: application/json' \
  --data-binary "@$TOKEN_PAYLOAD_FILE" \
  "${BASE_URL%/}/v1/chat/completions" >"$RESPONSE_FILE"; then
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
FINISH_REASON="$(jq -er '.choices[0].finish_reason' "$RESPONSE_FILE")"
[[ "$FINISH_REASON" == "stop" ]] || { printf 'invalid moderator finish reason: %s\n' "$FINISH_REASON" >&2; exit 1; }
printf 'finishReason: %s\n' "$FINISH_REASON" >>"$CAPTURE_FILE"
append_yaml_block "rawResponse" <(jq -r '.choices[0].message.content' "$RESPONSE_FILE")

YAML_RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$INPUT_FILE" "$MESSAGES_FILE" "$RESPONSE_FILE" "$VALIDATION_FILE" "$TOKEN_RESPONSE_FILE" "$TOKEN_PAYLOAD_FILE" "$YAML_RESPONSE_FILE"' EXIT
extract_yaml_verdict() {
  local decision="" decision_reason="" count=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      "decision: "*) decision="${line#decision: }"; ((count += 1)) ;;
      "reason: "*) decision_reason="${line#reason: }"; ((count += 1)) ;;
      *) printf 'invalid moderator YAML line\n' >&2; return 1 ;;
    esac
  done
  [[ "$count" == 2 && -n "$decision" && -n "$decision_reason" ]] || {
    printf 'incomplete moderator YAML response\n' >&2
    return 1
  }
  printf 'decision: %s\nreason: %s\n' "$decision" "$decision_reason"
}

jq -r '.choices[0].message.content' "$RESPONSE_FILE" | extract_yaml_verdict >"$YAML_RESPONSE_FILE"

validate_yaml_verdict() {
  local decision="" decision_reason=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      "decision: "*) decision="${line#decision: }" ;;
      "reason: "*) decision_reason="${line#reason: }" ;;
      "") ;;
      *) printf 'invalid YAML verdict line: %s\n' "$line" >&2; return 1 ;;
    esac
  done <"$YAML_RESPONSE_FILE"
  [[ "$decision" == "PASS" || "$decision" == "CONTINUE_PROGRESS" || "$decision" == "CONTINUE_NO_PROGRESS" || "$decision" == "BLOCKED" ]] || { printf 'invalid moderator decision\n' >&2; return 1; }
  [[ "$decision_reason" == "COMPLETE" || "$decision_reason" == "WORK_REMAINS" || "$decision_reason" == "NO_PROGRESS" || "$decision_reason" == "EXTERNAL_BLOCKER" || "$decision_reason" == "CLARIFICATION_REQUIRED" ]] || { printf 'invalid moderator reason code\n' >&2; return 1; }
  case "$decision:$decision_reason" in
    PASS:COMPLETE|CONTINUE_PROGRESS:WORK_REMAINS|CONTINUE_NO_PROGRESS:WORK_REMAINS|CONTINUE_NO_PROGRESS:NO_PROGRESS|BLOCKED:EXTERNAL_BLOCKER|BLOCKED:CLARIFICATION_REQUIRED) ;;
    *) printf 'invalid moderator decision and reason combination\n' >&2; return 1 ;;
  esac
  printf 'decision: %s\nreason: %s\n' "$decision" "$decision_reason"
}

validate_yaml_verdict

import test from "node:test";
import assert from "node:assert/strict";
import { CONTINUATION_LINE, OPERATOR_LINE, STATUS_AWAITING_USER, STATUS_COMPLETE, STATUS_USER_STOP, statusLine } from "../src/prompt.ts";

test("status line matches the verdict", () => {
  assert.equal(statusLine({ decision: "AGENT_COMPLETE", reasonCode: "WORK_COMPLETE" }), STATUS_COMPLETE);
  assert.equal(statusLine({ decision: "AGENT_STOPPED", reasonCode: "USER_STOP" }), STATUS_USER_STOP);
  assert.equal(statusLine({ decision: "AGENT_BLOCKED", reasonCode: "AWAITING_USER" }), STATUS_AWAITING_USER);
  assert.equal(statusLine({ decision: "AGENT_BLOCKED", reasonCode: "AWAITING_OPERATOR" }), OPERATOR_LINE);
  assert.equal(statusLine({ decision: "AGENT_CONTINUING", reasonCode: "WORK_REMAINS" }), CONTINUATION_LINE);
  assert.equal(statusLine({ decision: "AGENT_STALLED", reasonCode: "NO_PROGRESS" }), CONTINUATION_LINE);
});

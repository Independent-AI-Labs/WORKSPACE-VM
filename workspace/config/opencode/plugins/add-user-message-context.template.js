const RULES: Array<{ regex: RegExp; instruction: string }> = [
  {
    regex: /.+/,
    instruction:
      "## DO NOT JUMP TO CONCLUSIONS WITHOUT EXHAUSTING ALL ONLINE (EXA SEARCH) AND LOCAL (DOCUMENTATION, SOURCE CODE, ETC.) RESOURCES - MAKE SURE YOU HAVE ENOUGH KNOWLEDGE BEFORE GEENRATING A RESPONSE. BE PROACTIVE!!!",
  },
  {
    regex: /.+/,
    instruction:
      "## ALWAYS TAKE THE PROPER, LONG ROUTE EVEN WHEN YOU DON'T FEEL LIKE IT",
  },
  {
    regex: /.+/,
    instruction:
      "## DO THE CORRECT THING EVEN IF IT MEANS MORE EFFORT! MORE EFFORT IS GREAT - IT LEADS TO BETTER RESULTS!!! PREFER TO SURGICALLY EDIT FILES INSTEAD OF OVERWRITING THEM!!! BE RESPONSIBLE AND MOVE SLOW!!!",
  },
  {
    regex: /.+/,
    instruction:
      "## NEVER USE THE WORDS LIKELY, MAYBE, POSSIBLY, PROBABLY, PERHAPS, UNCLEAR, UNSURE IN YOUR ANSWERS - ALWAYS DO ACTUAL WORK FIRST AND ACQUIRE THEN VERIFY EVERY PIECE OF INFORMATION YOU NEED TO DELIVER A TRUTHFUL ANSWER!!!",
  },
]

const BLOCK_PATTERNS: Array<{ regex: RegExp; instruction: string }> = [
  {
    regex: /\b(likely|may[bB][eE]|possibly|probably|perhaps|unclear|unsure|i think|i believe|might be|could be)\b/i,
    instruction:
      "## STOP - your last response used speculation words. VERIFY EVERY CLAIM WITH ACTUAL EVIDENCE BEFORE ANSWERING. NEVER GUESS.",
  },
]

let matched: string[] = []

export const amiContext = async () => {
  return {
    "experimental.chat.messages.transform": async (
      _input: {},
      output: { messages: Array<{ info: { role: string }; parts: Array<{ type: string; text?: string }> }> },
    ) => {
      matched = []
      const seen = new Set<string>()
      for (const msg of output.messages) {
        if (msg.info.role === "user") {
          for (const part of msg.parts) {
            if (part.type !== "text" || !part.text?.trim()) continue
            for (const rule of RULES) {
              if (rule.regex.test(part.text) && !seen.has(rule.instruction)) {
                seen.add(rule.instruction)
                matched.push(rule.instruction)
              }
            }
          }
        } else if (msg.info.role === "assistant") {
          for (const part of msg.parts) {
            if (part.type !== "text" || !part.text?.trim()) continue
            for (const bp of BLOCK_PATTERNS) {
              if (bp.regex.test(part.text) && !seen.has(bp.instruction)) {
                seen.add(bp.instruction)
                matched.push(bp.instruction)
              }
            }
          }
        }
      }
    },

    "experimental.chat.system.transform": async (
      _input: { sessionID?: string; model: unknown },
      output: { system: string[] },
    ) => {
      for (const inst of matched) {
        output.system.push(inst)
      }
    },
  }
}

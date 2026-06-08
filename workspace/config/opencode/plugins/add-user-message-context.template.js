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
        if (msg.info.role !== "user") continue
        for (const part of msg.parts) {
          if (part.type !== "text" || !part.text?.trim()) continue
          for (const rule of RULES) {
            if (rule.regex.test(part.text) && !seen.has(rule.instruction)) {
              seen.add(rule.instruction)
              matched.push(rule.instruction)
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

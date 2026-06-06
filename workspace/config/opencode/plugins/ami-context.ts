const RULES: Array<{ regex: RegExp; instruction: string }> = [
  {
    regex: /.+/,
    instruction:
      "## DO NOT JUMP TO CONCLUSIONS WITHOUT EXHAUSTING ALL ONLINE (EXA SEARCH) AND LOCAL (DOCUMENTATION, SOURCE CODE, ETC.) RESOURCES - MAKE SURE YOU HAVE ENOUGH KNOWLEDGE BEFORE GEENRATING A RESPONSE. BE PROACTIVE!!!",
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

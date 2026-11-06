# Local moderator model probe

Date: 2026-11-05

Those runs used a hand-set 2048 context. That flag is removed. Context comes from `MODERATOR_CTX` (default 32768).

Ports: 8091, 8092, 8093. Two Arc A770s are present. Each server process mapped Vulkan.

## Results

Labeled cases: 27.

| Model | Match | Errors | Avg time | Total |
| --- | --- | --- | --- | --- |
| MiniCPM5-1B Q8_0 | 0/27 | 27/27 | 3230 ms | 87203 ms |
| MiniCPM5-2B FP8 Q8_0 | 0/27 | 27/27 | 709 ms | 19154 ms |
| LFM2.5-8B-A1B Q4_K_M | 0/27 | 27/27 | 1987 ms | 53659 ms |

None returned a legal `moderator_verdict` tool call. 1B returned prose. 2B returned an empty tool input. 8B dropped the stream after the first case.

gpt-5.6-luna labeled gate on the prior run: 27/27.

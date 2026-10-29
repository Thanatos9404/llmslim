/**
 * Real output of llmslim 0.12.0 for the home page, copied from the 0.12.0 launch trailer's data
 * (output/video/promo/audio/make_launch012_data.py, src/launch012/data.json). The script stores the 16 turns below in
 * a fresh SQLite memory with `Memory.add(..., user_id="dev", timestamp=...)` and asks three questions with
 * `Memory.search` (lexical relevance, the default: no model, no network). `SWEEP` asks the plan question at every
 * budget from 30 to 300 tokens. Nothing here is edited by hand; regenerate it from that script instead.
 */

export type StoredTurn = { at: string; role: "user" | "assistant"; text: string }

export type Recall = {
  question: string
  budget: number
  /** Tokens in `text`, never more than `budget`. */
  tokens: number
  /** Tokens in the whole stored history. */
  historyTokens: number
  /** How many standing requests, stated preferences and possibly conflicting statements came back. */
  requests: number
  preferences: number
  conflicts: number
  /** The context exactly as `Memory.search` returned it. */
  text: string
}

export const DEMO_VERSION = "0.12.0"

/** The 16 stored turns, in the order they were added. */
export const STORED_TURNS: readonly StoredTurn[] = [
  { at: "2026-09-02T10:14", role: "user", text: "Always include the rollback command when I ask about a deploy." },
  { at: "2026-09-02T10:14", role: "assistant", text: "Noted. Every deploy plan will end with its rollback command." },
  { at: "2026-09-03T16:40", role: "user", text: "I prefer pnpm over npm, and I'd rather ship small PRs." },
  { at: "2026-09-03T16:41", role: "assistant", text: "Got it: pnpm, and one change per PR." },
  { at: "2026-09-10T09:05", role: "user", text: "I have never deployed on a Friday. Not once." },
  { at: "2026-09-10T09:06", role: "assistant", text: "A good rule. Fridays stay quiet." },
  { at: "2026-09-22T14:30", role: "user", text: "The search service runs on Fly.io in two regions, ams and sjc." },
  { at: "2026-09-22T14:31", role: "assistant", text: "Two regions noted: ams and sjc." },
  { at: "2026-10-08T11:02", role: "user", text: "Staging deploys go through `pnpm deploy:staging`; prod is `pnpm deploy:prod`." },
  { at: "2026-10-08T11:03", role: "assistant", text: "Saved both commands." },
  { at: "2026-10-16T23:48", role: "user", text: "Deployed the billing hotfix to prod on Friday night. All green." },
  { at: "2026-10-16T23:49", role: "assistant", text: "Nice work. Billing is stable." },
  { at: "2026-10-21T08:20", role: "user", text: "Rollback for any service is `fly releases rollback` with the previous version." },
  { at: "2026-10-21T08:21", role: "assistant", text: "Rollback command saved." },
  { at: "2026-10-24T18:12", role: "user", text: "検索サービスは来週ベルリンにも展開する予定です。" },
  { at: "2026-10-24T18:13", role: "assistant", text: "Berlin is next for search." },
]

/** A request for help: the standing request and the stated preference come back in their own sections. */
export const PLAN_RECALL: Recall = {
  question: "Help me plan Friday's deploy of the search service.",
  budget: 300,
  tokens: 284,
  historyTokens: 474,
  requests: 1,
  preferences: 1,
  conflicts: 0,
  text: "Requests the user made earlier:\n- [2026-09-02 (Wed) 10:14] Always include the rollback command when I ask about a deploy.\n\nPreferences the user stated earlier:\n- [2026-09-03 (Thu) 16:40] I prefer pnpm over npm, and I'd rather ship small PRs.\n\n[2026-09-02 (Wed) 10:14] user: Always include the rollback command when I ask about a deploy.\n[2026-09-02] assistant: Noted. Every deploy plan will end with its rollback command.\n\n[2026-09-22 (Tue) 14:30] user: The search service runs on Fly.io in two regions, ams and sjc.\n[2026-09-22 (Tue) 14:31] assistant: Two regions noted: ams and sjc.\n\n[2026-10-08 (Thu) 11:03] assistant: Saved both commands.\n\n[2026-10-21 (Wed) 08:20] user: Rollback for any service is `fly releases rollback` with the previous version.\n[2026-10-21 (Wed) 08:21] assistant: Rollback command saved.\n\n[2026-10-24 (Sat) 18:13] assistant: Berlin is next for search.",
}

/** A question about the past: statements that may conflict come back side by side, in date order. */
export const HISTORY_RECALL: Recall = {
  question: "Have I ever deployed on a Friday?",
  budget: 300,
  tokens: 270,
  historyTokens: 474,
  requests: 0,
  preferences: 0,
  conflicts: 2,
  text: "Statements the user made on this that may conflict (in date order):\n- [2026-09-10 (Thu) 09:05] I have never deployed on a Friday.\n- [2026-10-16 (Fri) 23:48] Deployed the billing hotfix to prod on Friday night.\n\n[2026-09-02 (Wed) 10:14] user: Always include the rollback command when I ask about a deploy.\n[2026-09-02] assistant: Noted. Every deploy plan will end with its rollback command.\n\n[2026-09-10 (Thu) 09:05] user: I have never deployed on a Friday. Not once.\n[2026-09-10 (Thu) 09:06] assistant: A good rule. Fridays stay quiet.\n\n[2026-09-22 (Tue) 14:31] assistant: Two regions noted: ams and sjc.\n\n[2026-10-08 (Thu) 11:02] user: Staging deploys go through `pnpm deploy:staging`; prod is `pnpm deploy:prod`.\n\n[2026-10-16 (Fri) 23:48] user: Deployed the billing hotfix to prod on Friday night. All green.",
}

/** A question in Japanese, matched on its letters. */
export const JAPANESE_RECALL: Recall = {
  question: "検索サービスはどこに展開しますか？",
  budget: 120,
  tokens: 96,
  historyTokens: 474,
  requests: 0,
  preferences: 0,
  conflicts: 0,
  text: "[2026-09-02 (Wed) 10:14] user: Always include the rollback command when I ask about a deploy.\n[2026-09-02] assistant: Noted. Every deploy plan will end with its rollback command.\n\n[2026-10-24 (Sat) 18:12] user: 検索サービスは来週ベルリンにも展開する予定です。",
}

/** [budget, tokens returned] for the plan question at each budget from 30 to 300 tokens. */
export const SWEEP: readonly (readonly [budget: number, tokens: number])[] = [
  [30, 23], [31, 23], [32, 30], [33, 30], [34, 30], [35, 30], [36, 30], [37, 30], [38, 30], [39, 30], [40, 30], [41, 30],
  [42, 30], [43, 30], [44, 30], [45, 30], [46, 30], [47, 30], [48, 30], [49, 30], [50, 30], [51, 30], [52, 30], [53, 30],
  [54, 30], [55, 51], [56, 51], [57, 52], [58, 52], [59, 52], [60, 52], [61, 52], [62, 52], [63, 52], [64, 56], [65, 56],
  [66, 57], [67, 57], [68, 64], [69, 64], [70, 64], [71, 64], [72, 64], [73, 64], [74, 64], [75, 64], [76, 64], [77, 64],
  [78, 64], [79, 64], [80, 64], [81, 64], [82, 64], [83, 64], [84, 64], [85, 64], [86, 64], [87, 64], [88, 64], [89, 64],
  [90, 64], [91, 85], [92, 86], [93, 87], [94, 87], [95, 87], [96, 87], [97, 87], [98, 87], [99, 87], [100, 87], [101, 87],
  [102, 87], [103, 87], [104, 87], [105, 87], [106, 87], [107, 87], [108, 87], [109, 87], [110, 87], [111, 87], [112, 87], [113, 87],
  [114, 87], [115, 87], [116, 108], [117, 109], [118, 109], [119, 109], [120, 92], [121, 113], [122, 109], [123, 109], [124, 109], [125, 109],
  [126, 109], [127, 109], [128, 109], [129, 109], [130, 120], [131, 120], [132, 120], [133, 120], [134, 120], [135, 120], [136, 108], [137, 129],
  [138, 129], [139, 131], [140, 131], [141, 131], [142, 131], [143, 131], [144, 131], [145, 136], [146, 136], [147, 136], [148, 136], [149, 136],
  [150, 136], [151, 136], [152, 136], [153, 136], [154, 141], [155, 141], [156, 142], [157, 142], [158, 142], [159, 142], [160, 142], [161, 142],
  [162, 142], [163, 142], [164, 142], [165, 142], [166, 142], [167, 142], [168, 142], [169, 142], [170, 142], [171, 142], [172, 142], [173, 163],
  [174, 163], [175, 165], [176, 165], [177, 165], [178, 165], [179, 165], [180, 165], [181, 165], [182, 165], [183, 165], [184, 165], [185, 165],
  [186, 174], [187, 174], [188, 174], [189, 174], [190, 174], [191, 174], [192, 179], [193, 179], [194, 180], [195, 180], [196, 180], [197, 180],
  [198, 180], [199, 180], [200, 180], [201, 180], [202, 180], [203, 180], [204, 180], [205, 180], [206, 180], [207, 180], [208, 180], [209, 180],
  [210, 180], [211, 201], [212, 201], [213, 203], [214, 203], [215, 203], [216, 203], [217, 203], [218, 203], [219, 203], [220, 203], [221, 203],
  [222, 203], [223, 203], [224, 203], [225, 203], [226, 203], [227, 203], [228, 203], [229, 203], [230, 203], [231, 203], [232, 203], [233, 203],
  [234, 203], [235, 203], [236, 224], [237, 224], [238, 224], [239, 224], [240, 224], [241, 224], [242, 224], [243, 224], [244, 224], [245, 224],
  [246, 224], [247, 224], [248, 224], [249, 231], [250, 231], [251, 231], [252, 231], [253, 231], [254, 231], [255, 231], [256, 231], [257, 231],
  [258, 236], [259, 236], [260, 236], [261, 236], [262, 236], [263, 236], [264, 236], [265, 236], [266, 236], [267, 236], [268, 236], [269, 236],
  [270, 236], [271, 257], [272, 257], [273, 257], [274, 257], [275, 257], [276, 257], [277, 257], [278, 257], [279, 257], [280, 257], [281, 257],
  [282, 257], [283, 257], [284, 257], [285, 257], [286, 257], [287, 257], [288, 257], [289, 257], [290, 257], [291, 257], [292, 257], [293, 257],
  [294, 257], [295, 257], [296, 257], [297, 281], [298, 282], [299, 282], [300, 284],
]

/** How many of the 271 sweep answers went over their budget. */
export const SWEEP_OVER = 0

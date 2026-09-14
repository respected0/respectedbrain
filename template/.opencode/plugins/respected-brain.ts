/**
 * Respected Brain — OpenCode plugin (V1 + V2 dual)
 *
 * V1 (stabil opencode): default.server() / named export → Hooks
 * V2 (opencode2):       default.setup(ctx) → session.hook + event.subscribe
 *
 * Ortak motor: .beyin/hooks/bridge.py → lifecycle.py
 * SessionStart context: V1 system.transform / V2 context hook (bir kez)
 */

import { spawnSync } from "child_process"
import { join, dirname } from "path"
import { existsSync } from "fs"

const PLUGIN_ID = "respected-brain"
const MARKERS = [".respectedbrain-version", ".beyin-version"] as const

const pendingStart = new Map<string, string>()
const startInjected = new Set<string>()
const pendingNudge = new Map<string, string>()

function findVault(start: string): string | null {
  let dir = start
  for (let i = 0; i < 12; i++) {
    for (const m of MARKERS) {
      if (existsSync(join(dir, m))) return dir
    }
    if (existsSync(join(dir, ".beyin", "hooks", "bridge.py"))) return dir
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return null
}

function pyArgv(): string[] {
  return process.platform === "win32" ? ["py", "-3"] : ["python3"]
}

function inVault(vault: string, cwd: string): boolean {
  const v = vault.replace(/\\/g, "/").toLowerCase()
  const c = cwd.replace(/\\/g, "/").toLowerCase()
  return c === v || c.startsWith(v + "/")
}

type BeyinEvent = "start" | "prompt" | "end" | "precompact" | "postcompact"

function runBridge(
  vault: string,
  event: BeyinEvent,
  opts: { global?: boolean; cwd?: string; sessionId?: string } = {},
): string {
  const script = join(vault, ".beyin", "hooks", "bridge.py")
  if (!existsSync(script)) return ""
  const py = pyArgv()
  const args = [script, "--provider", "opencode", "--event", event]
  if (opts.global) args.push("--global-hook")
  const result = spawnSync(py[0], [...py.slice(1), ...args], {
    encoding: "utf-8",
    timeout: 20000,
    cwd: vault,
    input: JSON.stringify({
      cwd: opts.cwd || process.cwd(),
      session_id: opts.sessionId || `opencode-${process.pid}`,
    }),
    windowsHide: true,
  })
  if (result.error || (result.status !== 0 && result.status !== null)) return ""
  return (result.stdout || "").trim()
}

function extractContext(stdout: string): string {
  if (!stdout) return ""
  try {
    const data = JSON.parse(stdout)
    const value =
      data?.hookSpecificOutput?.additionalContext ??
      data?.additionalContext ??
      data?.additional_context ??
      data?.user_message ??
      ""
    return typeof value === "string" ? value.trim() : ""
  } catch {
    return stdout.length > 8 ? stdout.trim() : ""
  }
}

function mergeSystemStrings(system: string[], text: string, tag: string): void {
  if (!text || !system) return
  const block = `\n\n<!-- ${tag} -->\n${text}\n<!-- /${tag} -->\n`
  if (system.length > 0 && typeof system[0] === "string") {
    if (system[0].includes(`<!-- ${tag} -->`)) return
    system[0] = system[0] + block
    return
  }
  system.push(text)
}

function mergeSystemParts(system: unknown[], text: string, tag: string): void {
  if (!text || !Array.isArray(system)) return
  const marker = `<!-- ${tag} -->`
  for (const part of system) {
    if (
      part &&
      typeof part === "object" &&
      "text" in part &&
      typeof (part as { text: string }).text === "string" &&
      (part as { text: string }).text.includes(marker)
    ) {
      return
    }
  }
  system.push({ type: "text", text: `${marker}\n${text}\n<!-- /${tag} -->` })
}

function onSessionCreated(directory: string, sessionId: string | undefined): void {
  const vault = findVault(directory)
  if (!vault) return
  const global = !inVault(vault, directory)
  const text = extractContext(
    runBridge(vault, "start", { global, cwd: directory, sessionId }),
  )
  if (text && sessionId) {
    pendingStart.set(sessionId, text)
    startInjected.delete(sessionId)
  }
}

function onSessionEnd(directory: string, sessionId: string | undefined): void {
  const vault = findVault(directory)
  if (!vault) return
  const global = !inVault(vault, directory)
  runBridge(vault, "end", { global, cwd: directory, sessionId })
  if (sessionId) {
    pendingStart.delete(sessionId)
    startInjected.delete(sessionId)
    pendingNudge.delete(sessionId)
  }
}

function onPrompt(directory: string, sessionId: string | undefined): void {
  const vault = findVault(directory)
  if (!vault) return
  const global = !inVault(vault, directory)
  const nudge = extractContext(
    runBridge(vault, "prompt", { global, cwd: directory, sessionId }),
  )
  if (nudge && sessionId) pendingNudge.set(sessionId, nudge)
}

function onPrecompact(directory: string, sessionId: string | undefined): void {
  const vault = findVault(directory)
  if (!vault) return
  const global = !inVault(vault, directory)
  runBridge(vault, "precompact", { global, cwd: directory, sessionId })
}

function ensureStartContext(directory: string, sessionId: string): string {
  let text = pendingStart.get(sessionId)
  if (text) return text
  const vault = findVault(directory)
  if (!vault) return ""
  const global = !inVault(vault, directory)
  text = extractContext(
    runBridge(vault, "start", { global, cwd: directory, sessionId }),
  )
  if (text) pendingStart.set(sessionId, text)
  return text || ""
}

function injectStartOnce(
  directory: string,
  sessionId: string | undefined,
  apply: (text: string) => void,
): void {
  if (!sessionId || startInjected.has(sessionId)) return
  const text = ensureStartContext(directory, sessionId)
  if (!text) return
  apply(text)
  startInjected.add(sessionId)
  pendingStart.delete(sessionId)
}

function injectNudge(
  sessionId: string | undefined,
  apply: (text: string) => void,
): void {
  if (!sessionId) return
  const nudge = pendingNudge.get(sessionId)
  if (!nudge) return
  apply(nudge)
  pendingNudge.delete(sessionId)
}

function sessionIdFromProps(props?: Record<string, unknown>): string | undefined {
  if (!props) return undefined
  return (
    (props.sessionID as string) ||
    (props.sessionId as string) ||
    (props.id as string) ||
    undefined
  )
}

function buildV1Hooks(directory: string) {
  return {
    event: async ({
      event,
    }: {
      event: { type: string; properties?: Record<string, unknown> }
    }) => {
      try {
        const sid = sessionIdFromProps(event.properties)
        if (event.type === "session.created") onSessionCreated(directory, sid)
        else if (event.type === "session.deleted") onSessionEnd(directory, sid)
        else if (event.type === "session.idle") onSessionEnd(directory, sid)
        else if (event.type === "session.compacted") {
          const vault = findVault(directory)
          if (!vault) return
          runBridge(vault, "postcompact", {
            global: !inVault(vault, directory),
            cwd: directory,
            sessionId: sid,
          })
        }
      } catch {
        /* ignore */
      }
    },

    "chat.message": async (input: { sessionID?: string }) => {
      try {
        onPrompt(directory, input?.sessionID)
      } catch {
        /* ignore */
      }
    },

    "experimental.chat.system.transform": async (
      input: { sessionID?: string },
      output: { system: string[] },
    ) => {
      try {
        if (!output?.system) return
        injectStartOnce(directory, input?.sessionID, (text) =>
          mergeSystemStrings(
            output.system,
            text,
            "respected-brain-session-start",
          ),
        )
        injectNudge(input?.sessionID, (text) =>
          mergeSystemStrings(
            output.system,
            text,
            "respected-brain-prompt-nudge",
          ),
        )
      } catch {
        /* ignore */
      }
    },

    "experimental.session.compacting": async (
      input: { sessionID?: string },
      _output: { context?: string[] },
    ) => {
      try {
        onPrecompact(directory, input?.sessionID)
      } catch {
        /* ignore */
      }
    },
  }
}

async function setupV2(ctx: {
  location?: { directory?: string }
  directory?: string
  event?: {
    subscribe: (opts?: {
      signal?: AbortSignal
    }) => AsyncIterable<{
      type: string
      properties?: Record<string, unknown>
      data?: Record<string, unknown>
    }>
  }
  session?: {
    hook: (
      name: string,
      fn: (event: Record<string, unknown>) => void | Promise<void>,
      filter?: Record<string, unknown>,
    ) => Promise<{ dispose?: () => Promise<void> } | void>
  }
}) {
  const directory = ctx.location?.directory || ctx.directory || process.cwd()
  const controller = new AbortController()

  if (ctx.event?.subscribe) {
    void (async () => {
      try {
        for await (const ev of ctx.event!.subscribe({
          signal: controller.signal,
        })) {
          const props = (ev.properties || ev.data || {}) as Record<
            string,
            unknown
          >
          const sid = sessionIdFromProps(props)
          if (ev.type === "session.created") onSessionCreated(directory, sid)
          else if (ev.type === "session.deleted" || ev.type === "session.idle")
            onSessionEnd(directory, sid)
          else if (ev.type === "session.compacted") {
            const vault = findVault(directory)
            if (vault) {
              runBridge(vault, "postcompact", {
                global: !inVault(vault, directory),
                cwd: directory,
                sessionId: sid,
              })
            }
          }
        }
      } catch {
        /* aborted or unsupported stream */
      }
    })()
  }

  if (ctx.session?.hook) {
    await ctx.session.hook("context", (event) => {
      const sid = sessionIdFromProps(event as Record<string, unknown>)
      const system = event.system as unknown[] | undefined
      if (!system) return

      const applyStringOrPart = (text: string, tag: string) => {
        if (system.length && typeof system[0] === "string") {
          mergeSystemStrings(system as string[], text, tag)
        } else {
          mergeSystemParts(system, text, tag)
        }
      }

      injectStartOnce(directory, sid, (text) =>
        applyStringOrPart(text, "respected-brain-session-start"),
      )
      injectNudge(sid, (text) =>
        applyStringOrPart(text, "respected-brain-prompt-nudge"),
      )
    })

    try {
      await ctx.session.hook("prompt", (event) => {
        const sid = sessionIdFromProps(event as Record<string, unknown>)
        onPrompt(directory, sid)
      })
    } catch {
      /* older beta may lack prompt hook */
    }

    await ctx.session.hook("compaction", (event) => {
      const sid = sessionIdFromProps(event as Record<string, unknown>)
      onPrecompact(directory, sid)
    })
  }

  return () => controller.abort()
}

async function server(input?: { directory?: string }) {
  const directory = input?.directory || process.cwd()
  return buildV1Hooks(directory)
}

const dual = {
  id: PLUGIN_ID,
  async setup(ctx: Parameters<typeof setupV2>[0]) {
    return setupV2(ctx)
  },
  server,
}

export default dual

/** Legacy V1 named export (function form hosts) */
export const respectedBrainPlugin = async (input?: { directory?: string }) =>
  server(input)
// Two hooks for Orca Workstreams: guards that keep each state file written
// only by its owning script, PR reviews posted only by pr_review.py and
// unsaved work out of `orca worktree rm`, and a session-start check, through
// write_settings.py --read --check, that the stored Prompt Settings have not gone stale.

const STATUS_FILE = /(^|\/)\.orca\/prompts\/(.+\/)?[^/]*_status\.json$/
const BAND_FILE = /(^|\/)\.orca\/prompts\/_prompt-band\.json$/
const SETTINGS_FILE = /(^|\/)\.orca\/prompts\/prompt-settings\.json$/
const DECISIONS_FILE = /(^|\/)\.orca\/prompts\/.+\/_decisions\.md$/
const RESUME_FILE = /(^|\/)\.orca\/prompts\/.+\/_resume\.md$/
// Edit and Write on _config.json stay open: orca-prompt writes it before scaffold.py runs.
const CONFIG_FILE = /(^|\/)\.orca\/prompts\/.+\/_config\.json$/
const SETTINGS_PATH = '.orca/prompts/prompt-settings.json'
// A slow harness model listing in write_settings.py never delays session start past this.
export const SETTINGS_CHECK_MS = 5000

const PR_DENIAL = 'PR reviews, comments and reviewer assignments are posted by pr_review.py only. Run pr_review.py instead.'
// A gh api endpoint word pr_review.py writes to. A comment path with a PR
// number (group 1 the repo, group 2 the number) may also be the user's own PR.
const REVIEW_PATH = /^\/?repos\/[^/]+\/[^/]+\/(pulls\/[^/?]+\/(reviews|comments)|pulls\/comments|issues\/[^/?]+\/comments)([/?].*)?$/
const COMMENT_PATH = /^\/?repos\/([^/]+\/[^/]+)\/(?:pulls|issues)\/(\d+)\/comments(?:\/\d+\/replies)?\/?(?:\?.*)?$/
const QUERY = /^(?:--(?:raw-)?field=|-i*[fF]=?)?query=/
const MUTATION = /\bmutation\b.*\b(addPullRequestReview\w*|submitPullRequestReview|addComment|addAssigneesToAssignable)\b/s
const DENY = 'deny'

/**
 * The shell words of `command` with quotes and `\` escapes removed, so `"-f"`,
 * `-'f'` and `\-f` all read as `-f`. Unquoted blanks and `;&|()<>` end a word.
 * shortcut: `$'...'` escapes and variables stay unexpanded, so `$'\x2df'` or `$F` slip through; expand them if an agent uses them.
 * @param {string} command
 */
export const shellWords = command => {
  /** @type {string[]} */
  const words = []
  /** @type {string | undefined} */
  let word
  let quote = ''
  for (let i = 0; i < command.length; i++) {
    const c = command[i]
    if (quote === "'") {
      if (c === "'") quote = ''
      else word += c
    } else if (quote === '"') {
      if (c === '"') quote = ''
      else word += c === '\\' && '"\\$`'.includes(command[i + 1]) ? command[++i] : c
    } else if (c === "'" || c === '"') {
      word ??= ''
      quote = c
    } else if (c === '$' && (command[i + 1] === "'" || command[i + 1] === '"')) {
      word ??= ''
      quote = command[++i]
    } else if (c === '\\') {
      word = (word ?? '') + (command[++i] ?? '')
    } else if (/[\s;&|()<>]/.test(c)) {
      if (word !== undefined) words.push(word)
      word = undefined
    } else {
      word = (word ?? '') + c
    }
  }
  if (word !== undefined) words.push(word)
  return words
}

/**
 * Whether these words hold a `gh api` call with a body or a POST: a GET of the
 * same path is a read. `-f`/`-F` take attached and `=` values, and may follow
 * the boolean `-i` in one cluster; `-X` and `--method` take their value
 * attached, after `=` or as the next word.
 * @param {string[]} words
 */
export const apiWrites = words => {
  const start = words.findIndex((word, i) => word.split('/').pop() === 'gh' && words[i + 1] === 'api')
  return start >= 0 && words.slice(start + 2).some((word, i, rest) => {
    if (/^-i*[fF]/.test(word) || /^--(field|raw-field|input)(=|$)/.test(word)) return true
    const method = /^-i*X=?(.*)$/s.exec(word) ?? /^--method(?:=(.*))?$/s.exec(word)
    return method !== null && (method[1] || rest[i + 1] || '').toUpperCase() === 'POST'
  })
}

/** The script that alone writes `path`, or undefined for any other file. @param {string} path */
export const writerOf = path => {
  const posix = path.replaceAll('\\', '/')
  return STATUS_FILE.test(posix) ? 'set_status.py'
    : BAND_FILE.test(posix) ? 'set_prompt_band.py'
    : SETTINGS_FILE.test(posix) ? 'write_settings.py'
    : DECISIONS_FILE.test(posix) ? 'set_status.py log'
    : RESUME_FILE.test(posix) ? 'prepare.py'
    : undefined
}

// Every output redirect bash takes: `[N]>`, `[N]>>`, `[N]>|`, `&>`, `&>>` and `[N]>&`.
const REDIRECT = /(\d*>&|&>>?|\d*>>?\|?)\s*(\S+)/g

/** The files a Bash command writes through a redirect, `tee`, `sed -i`, `cp` or `mv`. @param {string} command */
export const bashTargets = command =>
  // A `|` right after `>` is the `>|` redirect, not a pipe.
  command.split(/&&|\|\||(?<!>)\||[;\n]/).flatMap(segment => {
    // `>&` onto a digit or `-` duplicates or closes a descriptor, so it writes no file.
    const redirects = [...segment.matchAll(REDIRECT)]
      .filter(([, op, target]) => !(op.endsWith('>&') && /^(\d+|-)$/.test(target)))
      .map(m => m[2])
    const words = segment.replace(REDIRECT, '').trim().split(/\s+/)
    const args = words.slice(1).filter(word => !word.startsWith('-'))
    const name = words[0]?.split('/').pop()
    // shortcut: cp checks only its last argument, so `cp -t <dir> <src>` slips through; parse -t if an agent uses it.
    const written = name === 'tee' || name === 'mv' || (name === 'sed' && words.some(w => /^-[a-zA-Z]*i/.test(w) || w.startsWith('--in-place')))
      ? args
      : name === 'cp' ? args.slice(-1) : []
    return [...redirects, ...written].map(path => path.replace(/^['"]|['"]$/g, ''))
  })

/**
 * The command with each heredoc body dropped: the body is text, so a body that
 * mentions `gh pr review` runs no gh. The `<<` line stays, with its redirects.
 * shortcut: a heredoc fed to `bash` or `sh` loses its commands too; keep the body if an agent runs gh that way.
 * @param {string} command
 */
export const stripHeredocs = command =>
  command.replace(/(?<!<)<<(?!<)(-?\s*(['"]?)(\w+)\2[^\n]*)\n(?:[\s\S]*?\n)?\t*\3(?=\n|$)/g, '<<$1')

/** The value of the call's `-R` or `--repo` flag, or undefined. @param {string[]} call */
const repoFlag = call => {
  for (const [i, word] of call.entries()) {
    const m = /^(?:-R=?|--repo(?:=|$))(.*)$/s.exec(word)
    if (m) return m[1] || call[i + 1]
  }
  return undefined
}

/**
 * What one `gh pr` call writes: DENY for a review or an assignment, the PR a
 * comment goes on, DENY when that PR cannot be read, or undefined for no write.
 * @param {string[]} call
 */
const prCallTarget = call => {
  let i = 2
  while (call[i]?.startsWith('-')) i += /^(-R|--repo)$/.test(call[i]) ? 2 : 1
  const sub = call[i]
  if (sub === 'review' || (sub === 'edit' && call.some(word => word.startsWith('--add-assignee')))) return DENY
  if (sub !== 'comment') return undefined
  const args = call.slice(i + 1)
  const pr = args.find((word, j) => !word.startsWith('-') && !/^(-b|--body|-F|--body-file|-R|--repo)$/.test(args[j - 1] ?? '')) ?? ''
  const url = /^https:\/\/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)\/?$/.exec(pr)
  if (url) return { repo: url[1], pr: url[2] }
  // A number-less `gh pr comment` picks the branch's PR, which the guard cannot see.
  return /^\d+$/.test(pr) ? { repo: repoFlag(call), pr } : DENY
}

/** What one `gh api` call writes, in the form prCallTarget returns. @param {string[]} call */
const apiCallTarget = call => {
  if (!apiWrites(call)) return undefined
  if (call.some(word => QUERY.test(word) && MUTATION.test(word))) return DENY
  const comment = call.map(word => COMMENT_PATH.exec(word)).find(Boolean)
  if (call.some(word => REVIEW_PATH.test(word) && !COMMENT_PATH.test(word))) return DENY
  // `{owner}/{repo}` is the current repo, as gh pr view reads it with no --repo.
  return comment ? { repo: comment[1].includes('{') ? undefined : comment[1], pr: comment[2] } : undefined
}

/**
 * The PR writes in these words: deny when one is a review, an assignment or a
 * comment on a PR the guard cannot name, else the PRs the comments go on.
 * @param {string[]} words @returns {{ deny: boolean, comments: { repo?: string, pr: string }[] }}
 */
export const prWrites = words => {
  const starts = words.flatMap((word, i) => (word.split('/').pop() === 'gh' ? [i] : []))
  const targets = starts.map((start, k) => {
    // The separators are gone, so a call runs to the next gh: extra words only add denials.
    const call = words.slice(start, starts[k + 1])
    return call[1] === 'pr' ? prCallTarget(call) : call[1] === 'api' ? apiCallTarget(call) : undefined
  }).filter(target => target !== undefined)
  return targets.includes(DENY)
    ? { deny: true, comments: [] }
    : { deny: false, comments: /** @type {{ repo?: string, pr: string }[]} */ (targets) }
}

/**
 * The worktree paths each `orca worktree rm` in these words names by a `path:`
 * or `id:` selector. An `id:` selector's path is the text after `::`.
 * @param {string[]} words
 */
export const worktreeRmPaths = words => {
  const isOrca = (/** @type {string | undefined} */ word) => /^orca(-dev|-ide)?$/.test(word?.split('/').pop() ?? '')
  return words.flatMap((word, i) => {
    if (!isOrca(word) || words[i + 1] !== 'worktree' || words[i + 2] !== 'rm') return []
    const rest = words.slice(i + 3)
    // The separators are gone, so a call runs to the next orca word.
    const end = rest.findIndex(isOrca)
    return rest.slice(0, end < 0 ? undefined : end).flatMap(arg => {
      const m = /^(?:--worktree=)?(path|id):(.+)$/s.exec(arg)
      return !m ? [] : m[1] === 'path' ? [m[2]] : [m[2].split('::').pop() ?? '']
    })
  })
}

/**
 * Why `orca worktree rm` on these paths would lose work: uncommitted changes,
 * commits not on the upstream, or no upstream at all. Undefined when none would.
 * @param {import('claude-code').Dollar} $ @param {string[]} paths
 */
export async function worktreeRmDenial($, paths) {
  for (const path of paths) {
    const git = (/** @type {string[]} */ args) => $.process.run(['git', '-C', path, ...args])
    const status = await git(['status', '--porcelain'])
    if (status.exitCode !== 0) return `${path} is not a git worktree the guard can read. Check the selector before orca worktree rm.`
    if (status.stdout.trim()) return `${path} has uncommitted changes. Commit and push them, or discard them, before orca worktree rm.`
    const ahead = await git(['rev-list', '@{upstream}..HEAD'])
    if (ahead.exitCode !== 0) return `${path} has no upstream, so its commits may exist nowhere else. Push the branch before orca worktree rm.`
    const count = ahead.stdout.trim().split('\n').filter(Boolean).length
    if (count > 0) return `${path} has ${count} commit(s) not on its upstream. Push them before orca worktree rm.`
  }
  return undefined
}

/** The unquoted shell words of a Bash command, heredoc bodies and `\` line breaks dropped. @param {string} raw */
export const commandWords = raw =>
  // A `\` line break continues the command, so `gh pr \` + `review` is one command.
  shellWords(stripHeredocs(raw).replace(/\\\r?\n/g, ' '))

/**
 * Why a Bash command is denied, and the PRs its comments go on, which may run
 * only when the signed-in gh user authored each one.
 * @param {string} raw @returns {{ denial?: string, comments: { repo?: string, pr: string }[] }}
 */
export const bashCheck = raw => {
  const command = stripHeredocs(raw).replace(/\\\r?\n/g, ' ')
  // Match on unquoted words, so quoting a flag or path never hides it.
  const { deny, comments } = prWrites(commandWords(raw))
  if (deny) return { denial: PR_DENIAL, comments: [] }
  for (const path of bashTargets(command)) {
    const writer = writerOf(path) ?? (CONFIG_FILE.test(path.replaceAll('\\', '/')) ? 'scaffold.py' : undefined)
    if (writer) return { denial: `${path} is written by ${writer} only. Run ${writer} instead of writing it from Bash.`, comments: [] }
  }
  return { comments }
}

/**
 * Whether the signed-in gh user authored every one of these PRs. A gh error
 * or an empty login reads as no.
 * @param {import('claude-code').Dollar} $ @param {{ repo?: string, pr: string }[]} targets
 */
export async function ownPrs($, targets) {
  const gh = async (/** @type {string[]} */ args) => {
    const ran = await $.process.run(['gh', ...args])
    if (ran.exitCode !== 0) throw new Error(ran.stderr)
    return ran.stdout.trim()
  }
  try {
    const me = await gh(['api', 'user', '--jq', '.login'])
    for (const { repo, pr } of targets) {
      const author = await gh(['pr', 'view', pr, ...(repo ? ['--repo', repo] : []), '--json', 'author', '--jq', '.author.login'])
      if (me === '' || author !== me) return false
    }
    return true
  } catch {
    return false
  }
}

/** @param {Parameters<import('claude-code').Register>[0]} on */
export function registerGuards(on) {
  for (const tool of /** @type {const} */ (['Edit', 'Write'])) {
    on('tool.call', { tool }, ($, e, next) => {
      const writer = writerOf(e.file_path)
      return writer
        ? { deny: `${$.plugin.name}: ${e.file_path} is written by ${writer} only. Run ${writer} instead of editing it.` }
        : next(e)
    }).catch(($, e, next) =>
      next.called ? next(e) : { deny: `${$.plugin.name}: its state file guard failed.` },
    )
  }
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const { denial, comments } = bashCheck(e.command)
    if (denial) return { deny: `${$.plugin.name}: ${denial}` }
    // A comment on the user's own PR, such as a reply to its reviewer, is theirs to post.
    if (comments.length > 0 && !(await ownPrs($, comments))) return { deny: `${$.plugin.name}: ${PR_DENIAL}` }
    const unsaved = await worktreeRmDenial($, worktreeRmPaths(commandWords(e.command)))
    if (unsaved) return { deny: `${$.plugin.name}: ${unsaved}` }
    return next(e)
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: `${$.plugin.name}: its Bash guard failed.` },
  )
}

/**
 * Shows one warning line when the stored Prompt Settings have gone stale, as
 * `write_settings.py --read --check` judges them: that script holds the one
 * copy of the checks. No stored settings is the ordinary first run.
 * @param {import('claude-code').Dollar} $ @param {string} cwd
 */
export async function warnStaleSettings($, cwd) {
  try {
    // Most repos store no settings: skip the python3 start-up there.
    if ((await $.fs.read(SETTINGS_PATH).catch(() => undefined)) === undefined) return
    const script = `${$.plugin.root}/skills/orca-prompt-settings/scripts/write_settings.py`
    const ran = await $.process.run(['python3', script, '--read', '--check', `${cwd}/${SETTINGS_PATH}`], { timeoutMs: SETTINGS_CHECK_MS })
    // A non-zero exit is no settings or a corrupt file: orca-prompt reports both itself. A timeout rejects into the catch.
    if (ran.exitCode !== 0) return
    const stale = ran.stdout.split('\n').filter(line => line.startsWith('STALE: ')).map(line => line.slice(7))
    if (stale.length > 0) {
      $.ui.log(`${$.plugin.name}: ${SETTINGS_PATH} has stale settings (${stale.join('; ')}). Run orca-prompt-settings to re-pick them.`)
    }
  } catch {
    // No python3, a timeout, or the check failed: nothing to warn about.
  }
}

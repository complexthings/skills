import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { OWNER, own } from './own.ts'

const SETTINGS = '.orca/prompts/prompt-settings.json'
// Answers $.fs beneath the plugin from these files, and records $.ui.log.
const world = (on: On, files: Record<string, unknown>) => {
  const logged: string[] = []
  const reads: string[] = []
  on('fs.read', async ($, e) => {
    if (e.path.endsWith('.owner')) return { value: OWNER }
    // $.fs resolves a relative path against the working directory.
    const name = Object.keys(files).find(name => e.path.endsWith(`/${name}`))
    if (name === undefined) throw new Error(`ENOENT ${e.path}`)
    reads.push(name)
    return { value: JSON.stringify(files[name]) }
  })
  on('ui.log', async ($, e) => { logged.push(e.text); return { value: undefined } })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('env.get', async () => ({ value: undefined }) as never)
  on('session.turns', async () => ({ value: 0 }) as never)
  on('session.id', async () => ({ value: OWNER }) as never)
  return Object.assign(logged, { reads })
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const

describe('status guard', () => {
  for (const tool of ['Edit', 'Write'] as const) {
    test(`${tool} on a _status.json under .orca/prompts is denied`, async ($, on) => {
      on('tool.call', async () => ({ result: 'wrote' }) as never)
      const ran = await $.tool.call({
        tool, tool_use_id: 't1', file_path: '/repo/.orca/prompts/ws/_status.json',
        content: '{}', old_string: 'a', new_string: 'b',
      } as never)
      expect(ran.deny).toContain('set_status.py')
    })
  }

  for (const tool of ['Edit', 'Write'] as const) {
    test(`${tool} on .orca/prompts/_prompt-band.json is denied`, async ($, on) => {
      on('tool.call', async () => ({ result: 'wrote' }) as never)
      const ran = await $.tool.call({
        tool, tool_use_id: 't3', file_path: '/repo/.orca/prompts/_prompt-band.json',
        content: '{}', old_string: 'a', new_string: 'b',
      } as never)
      expect(ran.deny).toContain('set_prompt_band.py')
    })
  }

  for (const tool of ['Edit', 'Write'] as const) {
    test(`${tool} on .orca/prompts/prompt-settings.json is denied`, async ($, on) => {
      on('tool.call', async () => ({ result: 'wrote' }) as never)
      const ran = await $.tool.call({
        tool, tool_use_id: 't4', file_path: '/repo/.orca/prompts/prompt-settings.json',
        content: '{}', old_string: 'a', new_string: 'b',
      } as never)
      expect(ran.deny).toContain('write_settings.py')
    })
  }

  for (const [file, writer] of [['_decisions.md', 'set_status.py log'], ['_resume.md', 'prepare.py']]) {
    for (const tool of ['Edit', 'Write'] as const) {
      test(`${tool} on a Workstream's ${file} is denied, naming ${writer}`, async ($, on) => {
        on('tool.call', async () => ({ result: 'wrote' }) as never)
        const ran = await $.tool.call({
          tool, tool_use_id: 't6', file_path: `/repo/.orca/prompts/ws/${file}`,
          content: '{}', old_string: 'a', new_string: 'b',
        } as never)
        expect(ran.deny).toContain(`written by ${writer} only`)
      })
    }
  }

  test('other files pass through', async ($, on) => {
    on('tool.call', async () => ({ result: 'wrote' }) as never)
    for (const file_path of ['/repo/.orca/prompts/ws/_config.json', '/repo/notes/_status.json', '/repo/notes/_prompt-band.json', '/repo/notes/_decisions.md', '/repo/docs/_resume.md']) {
      const ran = await $.tool.call({
        tool: 'Write', tool_use_id: 't2', file_path, content: '{}',
      } as never)
      expect(ran.deny).toBeUndefined()
    }
  })
})

describe('Bash guard', () => {
  const bash = (command: string) => ({ tool: 'Bash', tool_use_id: 't5', command }) as never
  // gh answers as the user `me`, who authored PR 7 only; `fail` makes every gh call exit 1.
  const gh = (on: On, fail = false) => {
    const runs: string[][] = []
    on('process.run', async ($, e) => {
      runs.push([...e.argv])
      const stdout = e.argv.includes('user') ? 'me\n' : e.argv[3] === '7' ? 'me\n' : 'someone\n'
      return { value: { exitCode: fail ? 1 : 0, stdout, stderr: '' } } as never
    })
    on('tool.call', async () => ({ result: 'ran' }) as never)
    return runs
  }
  const writes: [string, string][] = [
    ['echo {} > .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} 1> .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} &> .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} &>> .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} 2> .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} >| .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} >&.orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} >& .orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} 3>.orca/prompts/ws/_status.json', 'set_status.py'],
    ['echo {} 2>&1 >| .orca/prompts/ws/_status.json', 'set_status.py'],
    ['cat band >> .orca/prompts/_prompt-band.json', 'set_prompt_band.py'],
    ['echo "### x" >> .orca/prompts/ws/_decisions.md', 'set_status.py log'],
    ['echo resume > .orca/prompts/ws/_resume.md', 'prepare.py'],
    ['echo {} | tee .orca/prompts/prompt-settings.json', 'write_settings.py'],
    ["sed -i '' s/a/b/ .orca/prompts/ws/_config.json", 'scaffold.py'],
    ['cp /tmp/config.json .orca/prompts/ws/_config.json', 'scaffold.py'],
    ['mv /tmp/status.json .orca/prompts/ws/_status.json', 'set_status.py'],
    ["cat <<'EOF' > .orca/prompts/ws/_status.json\n{}\nEOF", 'set_status.py'],
  ]
  for (const [command, writer] of writes) {
    test(`${command} is denied, naming ${writer}`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toContain(`written by ${writer} only`)
    })
  }

  const prWrites = [
    'gh pr review 12 --approve',
    'gh pr comment 12 --body done',
    'gh pr edit 12 --add-assignee @me',
    'gh api repos/o/r/pulls/12/reviews -f event=COMMENT',
    'gh api repos/o/r/pulls/12/comments -f body=x',
    'gh api repos/o/r/issues/12/comments -f body=x',
    'gh api repos/o/r/pulls/5/comments -fbody=x',
    'gh api repos/o/r/pulls/5/comments -Fbody=x',
    'gh pr -R o/r review 5 --approve',
    'gh pr --repo=o/r comment 5 --body x',
    'gh pr \\\n  review 5 --approve',
    'gh pr review 5 --approve # pr_review.py',
    'python3 /p/skills/orca-pr-review/scripts/pr_review.py post 12 && gh pr comment 12 --body done',
    'gh api -X POST repos/o/r/pulls/5/reviews --input r.json',
    `gh api graphql -f query='mutation { addPullRequestReview(input: {pullRequestId: "x", event: APPROVE}) { clientMutationId } }'`,
    'gh api "repos/o/r/pulls/5/comments" "-f" body=x',
    "gh api 'repos/o/r/pulls/5/comments' -f body=x",
    'gh "pr" "review" 5 --approve',
    `gh api repos/o/r/pulls/5/comments $'-f' body=x`,
    'gh api repos/o/r/pulls/5/comments $"-f" body=x',
    "gh api graphql -F query='\nmutation {\n  submitPullRequestReview(input: {}) { clientMutationId }\n}'",
  ]
  for (const command of prWrites) {
    test(`${command} is denied, naming pr_review.py`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toContain('pr_review.py')
    })
  }

  // Every spelling of each gh api write flag: separate, attached and `=` forms,
  // each bare, quoted whole, single-quoted and quoted after the dash.
  const quotings = (flag: string) => [flag, `"${flag}"`, `'${flag}'`, `-"${flag.slice(1)}"`, `\\${flag}`]
  const apiFlags = [
    '-f body=x', '-fbody=x', '-f=body=x', '-F body=x', '-Fbody=x', '-F=body=x', '-if body=x',
    '--field body=x', '--field=body=x', '--raw-field body=x', '--raw-field=body=x',
    '--input r.json', '--input=r.json',
    '-X POST', '-XPOST', '-X=POST', '-X post', '--method POST', '--method=POST', '--method post',
  ]
  const apiAllowed = ['-X GET', '-XGET', '--method=get', '--method GET', '--jq .f', '-q .f', '-H Accept:x', '--paginate', '-i']
  const quoted = (forms: string[]) => forms.flatMap(form => {
    const [flag, ...rest] = form.split(' ')
    return quotings(flag).map(word => [word, ...rest].join(' '))
  })
  for (const form of quoted(apiFlags)) {
    const command = `gh api repos/o/r/pulls/5/comments ${form}`
    test(`${command} is denied, naming pr_review.py`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toContain('pr_review.py')
    })
  }
  for (const command of [
    ...quoted(apiAllowed).map(form => `gh api repos/o/r/pulls/5/comments ${form}`),
    ...quoted(apiFlags).map(form => `gh api repos/o/r/issues ${form}`),
  ]) {
    test(`${command} runs`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toBeUndefined()
    })
  }

  const allowed = [
    'python3 /p/skills/orca-prompt/scripts/set_status.py .orca/prompts/ws --start >/dev/null 2>&1',
    'cat .orca/prompts/ws/_status.json',
    'cat .orca/prompts/ws/_status.json >&2',
    'cat .orca/prompts/ws/_status.json 2>&1 | head',
    'cat .orca/prompts/ws/_status.json >&-',
    'cp .orca/prompts/ws/_config.json /tmp/config.json',
    'gh pr view 12',
    'gh pr view 12 --comments',
    'gh pr -R o/r view 5',
    'gh api repos/o/r/pulls/5/comments',
    'gh api repos/o/r/pulls/5/reviews --jq .[].state',
    "gh api graphql -f query='{ repository(owner: \"o\", name: \"r\") { pullRequest(number: 5) { title } } }'",
  ]
  for (const command of allowed) {
    test(`${command} runs`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toBeUndefined()
    })
  }

  // PR 7 is the user's own: comments and replies on it pass, nothing else does.
  const ownComments = [
    'gh pr comment 7 --body done',
    'gh pr comment --body done 7',
    'gh pr comment https://github.com/o/r/pull/7 -b done',
    'gh api repos/o/r/pulls/7/comments/99/replies -f body=x',
    'gh api repos/o/r/pulls/7/comments -f body=x -f commit_id=abc -f path=a.js -F line=3',
    'gh api repos/o/r/issues/7/comments -f body=x',
    "gh api 'repos/{owner}/{repo}/pulls/7/comments/99/replies' -f body=x",
  ]
  for (const command of ownComments) {
    test(`${command} runs on the user's own PR`, async ($, on) => {
      const runs = gh(on)
      expect((await $.tool.call(bash(command))).deny).toBeUndefined()
      expect(runs.at(-1)?.slice(0, 4)).toEqual(['gh', 'pr', 'view', '7'])
    })
  }

  test('the PR view names the repo the command names', async ($, on) => {
    const runs = gh(on)
    await $.tool.call(bash('gh pr comment 7 -R o/r -b x && gh api repos/a/b/pulls/7/comments/1/replies -f body=y'))
    expect(runs.slice(1).map(argv => argv.slice(3, 6))).toEqual([['7', '--repo', 'o/r'], ['7', '--repo', 'a/b']])
  })

  const ownDenied = [
    'gh pr review 7 --approve',
    'gh pr edit 7 --add-assignee @me',
    'gh api repos/o/r/pulls/7/reviews -f event=COMMENT',
    `gh api graphql -f query='mutation { addComment(input: {subjectId: "x", body: "y"}) { clientMutationId } }'`,
    'gh pr comment 7 -b x && gh pr comment 12 -b y',
    'gh pr comment -b x',
    'gh pr comment my-branch -b x',
    'gh api repos/o/r/pulls/comments/99 -X PATCH -f body=x',
  ]
  for (const command of ownDenied) {
    test(`${command} is denied even with an own PR in reach`, async ($, on) => {
      gh(on)
      expect((await $.tool.call(bash(command))).deny).toContain('pr_review.py')
    })
  }

  test("a comment on the user's own PR is denied when gh fails", async ($, on) => {
    gh(on, true)
    expect((await $.tool.call(bash('gh pr comment 7 --body done'))).deny).toContain('pr_review.py')
  })

  // A body that only mentions a blocked command is text, never a gh call.
  const mentions = [
    'gh issue create --title t --body "run gh pr review 5 --approve to ship"',
    "gh issue create --title t --body-file - <<'EOF'\ngh pr review 5 --approve\ngh api repos/o/r/pulls/5/comments -f body=x\nEOF",
    "gh api repos/o/r/issues -f title=t -f body='see repos/o/r/pulls/5/comments'",
    "gh api repos/o/r/issues -f title=t -f body='mutation { addComment(input: {}) { clientMutationId } }'",
  ]
  for (const command of mentions) {
    test(`${command} runs`, async ($, on) => {
      const runs = gh(on)
      expect((await $.tool.call(bash(command))).deny).toBeUndefined()
      expect(runs).toEqual([])
    })
  }
})

describe('worktree rm guard', () => {
  const bash = (command: string) => ({ tool: 'Bash', tool_use_id: 't7', command }) as never
  // git answers per worktree path: /wt/clean is pushed, the rest each lose work one way.
  const worktrees = (on: On) => {
    const runs: string[][] = []
    on('process.run', async ($, e) => {
      runs.push([...e.argv])
      const [, , path, cmd] = e.argv
      const answer = (exitCode: number, stdout = '') => ({ value: { exitCode, stdout, stderr: '' } }) as never
      if (path === '/wt/gone') return answer(128)
      if (cmd === 'status') return answer(0, path === '/wt/dirty' ? ' M a.txt\n' : '')
      if (path === '/wt/lone') return answer(128)
      return answer(0, path === '/wt/ahead' ? 'abc\ndef\n' : '')
    })
    on('tool.call', async () => ({ result: 'ran' }) as never)
    return runs
  }
  const denied: [string, string][] = [
    ['orca worktree rm --worktree "path:/wt/dirty" --json', '/wt/dirty has uncommitted changes'],
    ["orca worktree rm --worktree path:'/wt/dirty'", '/wt/dirty has uncommitted changes'],
    ["orca worktree rm --worktree 'id:repo-1::/wt/ahead' --json", '/wt/ahead has 2 commit(s) not on its upstream'],
    ['orca-dev worktree rm --worktree=path:/wt/lone', '/wt/lone has no upstream'],
    ['cd /x && /usr/local/bin/orca worktree rm --worktree path:/wt/gone', '/wt/gone is not a git worktree'],
    ['orca worktree rm --worktree path:/wt/clean && orca worktree rm --worktree path:/wt/dirty', '/wt/dirty has uncommitted changes'],
  ]
  for (const [command, reason] of denied) {
    test(`${command} is denied`, async ($, on) => {
      worktrees(on)
      expect((await $.tool.call(bash(command))).deny).toContain(reason)
    })
  }

  test('a clean, pushed worktree is removed', async ($, on) => {
    const runs = worktrees(on)
    expect((await $.tool.call(bash('orca worktree rm --worktree "path:/wt/clean" --json'))).deny).toBeUndefined()
    expect(runs).toEqual([['git', '-C', '/wt/clean', 'status', '--porcelain'], ['git', '-C', '/wt/clean', 'rev-list', '@{upstream}..HEAD']])
  })

  test('other orca worktree commands run no git', async ($, on) => {
    const runs = worktrees(on)
    for (const command of ['orca worktree list --json', 'orca worktree rm --worktree branch:main', 'git worktree remove path:/wt/dirty']) {
      expect((await $.tool.call(bash(command))).deny).toBeUndefined()
    }
    expect(runs).toEqual([])
  })
})

describe('stale settings warning', () => {
  // Answers write_settings.py with this exit code and stdout, and records each argv.
  const check = (on: On, exitCode: number, stdout: string) => {
    const runs: string[][] = []
    on('process.run', async ($, e) => {
      runs.push([...e.argv])
      timeouts.push((e as { init?: { timeoutMs?: number } }).init?.timeoutMs)
      return { value: { exitCode, stdout, stderr: '' } } as never
    })
    return runs
  }
  const timeouts: (number | undefined)[] = []

  test('gives the check a 5 second total timeout', async ($, on) => {
    const logged = world(on, { [SETTINGS]: {} })
    timeouts.length = 0
    check(on, 0, 'STALE: never read\n')
    await $.session.start(start)
    expect(timeouts.at(-1)).toBe(5000)
    expect(logged.length).toBe(1)
  })

  test('a check that times out shows nothing', async ($, on) => {
    const logged = world(on, { [SETTINGS]: {} })
    on('process.run', async () => { throw new Error('process.run timed out after 5000ms') })
    await $.session.start(start)
    expect(logged).toEqual([])
  })

  test('warns once, naming each stale setting the check prints', async ($, on) => {
    const logged = world(on, { [SETTINGS]: {} })
    const runs = check(on, 0, '{}\nSTALE: claude.subagent: claude-opus-4-1 is not in priority.json\nSTALE: harnesses: pi is not installed\n')
    await $.session.start(start)
    const ran = runs.filter(argv => argv[1]?.endsWith('/skills/orca-prompt-settings/scripts/write_settings.py'))
    expect(ran.map(argv => argv.slice(2))).toEqual([['--read', '--check', `/repo/${SETTINGS}`]])
    expect(logged.length).toBe(1)
    expect(logged[0]).toContain('claude.subagent: claude-opus-4-1 is not in priority.json; harnesses: pi is not installed')
  })

  test('stays quiet when nothing is stale', async ($, on) => {
    const logged = world(on, { [SETTINGS]: {} })
    check(on, 0, '{}\n')
    await $.session.start(start)
    expect(logged).toEqual([])
  })

  test('stays quiet on a corrupt settings file', async ($, on) => {
    const logged = world(on, { [SETTINGS]: {} })
    check(on, 1, 'FAIL: invalid Prompt Settings at .orca/prompts/prompt-settings.json: not valid JSON\n')
    await $.session.start(start)
    expect(logged).toEqual([])
  })

  test('runs no script without a settings file', async ($, on) => {
    const logged = world(on, {})
    const runs = check(on, 0, 'STALE: never read\n')
    await $.session.start(start)
    expect(runs.filter(argv => argv[1]?.endsWith('write_settings.py'))).toEqual([])
    expect(logged).toEqual([])
  })
})

// A Desktop session can load the module after session.start has fired, so
// the first band draw has to start the polls itself.
describe('bands without session.start', () => {
  const BAND = { component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 30, bodyColumns: 120 } } as never
  const STATUS = { workstream: 'Workstream Name', active: true, items: [{ id: 'a', title: 'Docs', wave: 1, state: 'todo', reason: null }] }
  const PROMPT_BAND = {
    step: 'basics', ended: false, updatedAt: new Date().toISOString(),
    steps: [{ id: 'basics', title: 'Basics', state: 'active', answers: {} }],
    checklist: [],
  }
  const bands = (on: On, files: Record<string, unknown>) => {
    on('fs.list', async () => ({ value: [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
    on('fs.read', async ($, e) => {
      if (e.path.endsWith('.owner')) return { value: OWNER }
      const name = Object.keys(files).find(name => e.path.endsWith(name))
      if (name === undefined) throw new Error(`ENOENT ${e.path}`)
      return { value: JSON.stringify(files[name]) }
    })
    on('config.list', async () => ({ value: [] }) as never)
    on('ui.render', { component: 'AbovePrompt' }, ($, e) => h($.ui.resolve(e).Text, {}, 'engine band') as never)
  }

  test('desktop: the Wave band draws on its first render', async ($, on) => {
    own(on)
    bands(on, { 'ws/_status.json': STATUS })
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'desktop', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeDefined()
    await ui.unmount()
  })

  test('desktop: the Prompt Band draws on its first render', async ($, on) => {
    own(on)
    bands(on, { '_prompt-band.json': PROMPT_BAND })
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'desktop', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })
})

// The question tool in the Owning Session opens an Attention Item through set_status.py, its result clears it (ADR 0014).
describe('Attention capture', () => {
  const STATUS = { workstream: 'ws', active: true, items: [{ id: 'a', title: 'Docs', wave: 1, state: 'todo', reason: null }] }
  const ASK = {
    tool: 'AskUserQuestion', tool_use_id: 'q1',
    questions: [{ question: 'Ship it?', header: 'Ship', multiSelect: false, options: [{ label: 'Yes', description: '' }, { label: 'No', description: '' }] }],
  } as never
  const world = (on: On, status: unknown = STATUS) => {
    const runs: string[][] = []
    const seen: number[] = []
    on('fs.list', async () => ({ value: [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
    on('fs.read', async ($, e) => {
      if (e.path.endsWith('.owner')) return { value: OWNER }
      if (e.path.endsWith('ws/_status.json')) return { value: JSON.stringify(status) }
      throw new Error(`ENOENT ${e.path}`)
    })
    on('process.run', async ($, e) => { runs.push([...e.argv]); return { value: { exitCode: 0, stdout: '', stderr: '' } } as never })
    // The dialog is open while the tool runs: record how many set_status calls came before its answer.
    on('tool.call', async () => { seen.push(runs.length); return { result: { answers: { 'Ship it?': 'Yes' } } } as never })
    return { runs, seen }
  }
  const args = (argv: string[]) => argv.slice(argv.findIndex(a => a.endsWith('set_status.py')) + 1)

  test('the Owning Session records the question, then clears it on the result', async ($, on) => {
    own(on)
    const { runs, seen } = world(on)
    const ran = await $.tool.call(ASK)
    expect(ran.deny).toBeUndefined()
    expect(seen).toEqual([1])
    expect(runs.map(args)).toEqual([
      ['.orca/prompts/ws', '--attention', 'question', 'Ship it?', 'Yes', 'No'],
      ['.orca/prompts/ws', '--attention', '--clear'],
    ])
  })

  test('a non-owning session writes nothing', async ($, on) => {
    const env = own(on)
    env.session = 'session-b'
    const { runs, seen } = world(on)
    await $.tool.call(ASK)
    expect(seen).toEqual([0])
    expect(runs).toEqual([])
  })

  test('no active Workstream writes nothing', async ($, on) => {
    own(on)
    const { runs } = world(on, { ...STATUS, active: false })
    await $.tool.call(ASK)
    expect(runs).toEqual([])
  })
})

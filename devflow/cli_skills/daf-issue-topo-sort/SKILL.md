---
name: daf-issue-topo-sort
description: "Dependency and conflict-aware issue ordering with topological sort"
user-invocable: true
---

# Issue Topology Sort

Topologically sort issues by explicit dependencies AND file conflict avoidance. Produces an ordered work plan with concurrent groups.

## Usage

```
/daf-issue-topo-sort [--repo owner/repo] [--label <label>] [--parent <JIRA-KEY>]
```

**GitHub**: `/daf-issue-topo-sort --repo owner/repo --label v1.0`
**GitHub (current repo)**: `/daf-issue-topo-sort --label v1.0`
**JIRA**: `/daf-issue-topo-sort --parent PROJ-123`

If no arguments given, ask the user which mode (GitHub or JIRA) and the required parameters.

---

## Step 1: Gather Issues

### GitHub

```bash
gh issue list --repo <repo> --label <label> --state open --json number,title,body,url --limit 100
```

If `--repo` not provided, use current repository (auto-detected from git remote).

For each issue, also fetch comments:

```bash
gh issue view <number> --repo <repo> --json comments --jq '.comments[].body'
```

### JIRA

Use MCP JIRA tools to fetch child issues of the parent:

```
mcp__mcp-atlassian__jira_search(
  jql="parent = <PARENT-KEY> AND status != Done ORDER BY key ASC",
  fields="summary,status,description,comment,issuelinks"
)
```

For each issue, also fetch full details including comments:

```
mcp__mcp-atlassian__jira_get_issue(issue_key=<KEY>, fields="*all", comment_limit=50)
```

**Output of this step**: A list of **open** issues only, each with: key/number, title, body/description, comments, and (for JIRA) existing issue links. Closed/done issues must never appear in this list or any subsequent step.

---

## Step 2: Analyze Each Issue

For each issue, extract two things:

### 2a. Explicit Dependencies

Scan issue body AND all comments for dependency patterns (case-insensitive):

| Pattern | Meaning |
|---------|---------|
| `depends on #X` / `depends on PROJ-X` | This issue depends on X |
| `after #X` / `after PROJ-X` | This issue should come after X |
| `needs #X first` / `needs PROJ-X first` | This issue needs X completed first |
| `blocked by #X` / `blocked by PROJ-X` | This issue is blocked by X |
| `requires #X` / `requires PROJ-X` | This issue requires X |
| `prerequisite: #X` / `prerequisite: PROJ-X` | X is a prerequisite |

Also check JIRA issue links for existing "Blocks" / "is blocked by" relationships.

### Functional Dependencies (inferred)

Beyond explicit textual references, analyze what each issue actually implements and determine if any issue requires functionality from another issue to work. This catches dependencies that nobody wrote down.

For each pair of issues, consider:
- Does issue A introduce a new API, model, config field, or utility that issue B would use or extend?
- Does issue A create infrastructure (new module, database table, service) that issue B builds on top of?
- Does issue A define a data format, protocol, or interface that issue B consumes?
- Would implementing issue B require code from issue A to already exist in the codebase?

If yes, add a functional dependency edge: B depends on A. Mark these as "inferred (functional)" to distinguish from explicit text references.

Example: If #100 "Add ConcurrencyConfig model" and #200 "Add concurrency section to TUI config editor" — #200 functionally depends on #100 even if neither issue mentions the other.

**Closed issue handling (CRITICAL)**: Before adding any dependency edge, verify the referenced issue is actually open. Use `gh issue view <number> --json state --jq '.state'` (GitHub) or check the issue status (JIRA). If the referenced issue is closed/done:
- Do NOT add it to the dependency graph
- Do NOT include it in the execution order or concurrent groups
- Note it as "(closed — dependency satisfied)" in the analysis output
- The depending issue loses that dependency edge (it may become unblocked)

This applies to both explicit dependencies AND file conflict detection — only open issues participate in the graph.

Build a dependency map (open issues only):
```
dependencies = {
  issue_key: [list of issues this one depends on]
}
```

### 2b. Involved Files

For each issue, determine which files it will modify. Use these approaches in order — each adds more accuracy:

1. **Extract explicit file paths** from issue body and comments (patterns like `src/foo/bar.py`, `lib/utils.ts`, any path with a file extension)
2. **Check for "Files Involved" sections** in comments (from prior runs of this skill)
3. **Investigate the codebase** to find files the issue would need to change. This is the most important step — issue descriptions rarely list every file. For each issue:
   - Read the issue title and description to understand what functionality is being changed
   - Use `grep` or `find` to locate relevant code (e.g., if the issue says "refactor hook processing", search for files containing hook processing logic)
   - Read key files to understand which modules are involved
   - Consider downstream files: if a function signature changes, find its callers
   - Consider test files: if `src/foo.py` changes, `tests/test_foo.py` likely changes too
   - List ALL files that would realistically need modification, not just the primary ones

**Be thorough** — missed files mean missed conflicts. Two issues that both modify `hook_processing.py` will cause merge conflicts if developed in parallel. The whole value of this skill depends on accurate file identification.

Build a file map:
```
involved_files = {
  issue_key: [list of file paths]
}
```

### 2c. Post Analysis Comment (requires approval)

**Ask the user for approval before posting comments to any issues.** Show the list of issues and their detected files, then ask: "Post 'Files Involved' comments to these issues? (yes/no)"

If approved, add a comment listing the involved files. This comment is for human reference only — always re-investigate on each run, never rely on prior comments.

**GitHub**:
```bash
gh issue comment <number> --repo <repo> --body "$(cat <<'EOF'
### Files Involved (auto-detected)

- `path/to/file1.py`
- `path/to/file2.py`

_Generated by issue-topo-sort skill_
EOF
)"
```

**JIRA**:
```
mcp__mcp-atlassian__jira_add_comment(
  issue_key=<KEY>,
  body="h3. Files Involved (auto-detected)\n\n* {{path/to/file1.py}}\n* {{path/to/file2.py}}\n\n_Generated by issue-topo-sort skill_"
)
```

---

## Step 3: Build Dependency Graph

Construct a graph with two types of edges:

### Dependency Edges (directed)

From Step 2a. If issue A depends on issue B, add edge B → A (B must come before A).

### Conflict Edges (undirected)

From Step 2b. If issue A and issue B both modify the same file(s), add a conflict edge between them. Record which file(s) cause the conflict.

```
conflict_edges = {
  (issue_A, issue_B): [list of shared files]
}
```

---

## Step 4: Topological Sort

Use Kahn's algorithm to produce an ordered list:

1. Calculate in-degree for each issue (count of dependency edges pointing to it)
2. Initialize queue with all issues having in-degree 0
3. While queue is not empty:
   a. Remove an issue from the queue
   b. Add it to the sorted output
   c. For each issue that depends on it, decrement in-degree; if zero, add to queue
4. If any issues remain (cycle detected), report the cycle and append them at the end

### Grouping for Concurrency

After sorting, group issues into concurrent execution groups:

- **Group 1**: All issues with no dependencies AND no conflict edges between them
- **Group 2**: Issues whose dependencies are all in Group 1, AND no conflict edges to other Group 2 members
- **Group N**: Continue until all issues are grouped

Within each group, issues can be developed in parallel. Between groups, issues must be sequential.

**Conflict edge handling**: Two issues with a conflict edge (same files) CANNOT be in the same concurrent group, even if they have no dependency relationship. Place the one with fewer dependencies in the earlier group.

### Cycle Detection

If a cycle is detected among dependency edges:

1. Report the cycle clearly: "Circular dependency: A → B → C → A"
2. Ask the user how to resolve (break which edge)
3. If user doesn't resolve, append cycled issues at the end with a warning

---

## Step 5: Set Relationships

**IMPORTANT: Always show the full list of proposed links to the user and ask for explicit approval BEFORE writing anything to JIRA or GitHub.** Display the links in a table format:

```
## Proposed Dependency Links

| From (blocks) | To (blocked by) | Reason |
|---------------|-----------------|--------|
| PROJ-101      | PROJ-102        | Explicit: "depends on PROJ-101" |
| #5            | #8              | File conflict: utils.py |

Create these links? (yes/no)
```

Only proceed if the user confirms. If the user says no or wants to modify, let them pick which links to create.

**Existing links policy (additive only)**: Before proposing links, check what dependency links already exist on each issue. Skip any link that already exists — never delete or replace existing dependencies. Only propose NEW links that don't exist yet. Show existing links separately so the user has visibility:

```
## Existing Dependency Links (unchanged)

| From (blocks) | To (blocked by) | Status     |
|---------------|-----------------|------------|
| #100          | #200            | Already set |

## New Dependency Links (proposed)

| From (blocks) | To (blocked by) | Reason |
|---------------|-----------------|--------|
| #300          | #400            | File conflict: utils.py |

Create these NEW links? (yes/no)
```

### JIRA

For each approved dependency edge (B blocks A), create an issue link:

```
mcp__mcp-atlassian__jira_create_issue_link(
  link_type="Blocks",
  inward_issue_key=<BLOCKER>,
  outward_issue_key=<BLOCKED>,
  comment="Dependency detected by issue-topo-sort"
)
```

**Important**: The JIRA link API is counterintuitive:
- For "A blocks B": `inward_issue_key=A`, `outward_issue_key=B`
- The `link_type` name must match exactly — fetch available types first if unsure:

```
mcp__mcp-atlassian__jira_get_link_types()
```

Skip links that already exist (check existing issue links from Step 1).

### GitHub

Use the `addBlockedBy` GraphQL mutation to create dependency relationships (NOT `addSubIssue` which creates parent-child sub-issues):

```bash
# Get node IDs for both issues
BLOCKED_ID=$(gh issue view <blocked_number> --repo <repo> --json id --jq '.id')
BLOCKER_ID=$(gh issue view <blocker_number> --repo <repo> --json id --jq '.id')

# Create "blocked by" relationship
gh api graphql -f query='
  mutation {
    addBlockedBy(input: {issueId: "'$BLOCKED_ID'", blockingIssueId: "'$BLOCKER_ID'"}) {
      clientMutationId
    }
  }
'
```

- `issueId` = the blocked issue (the one that must wait)
- `blockingIssueId` = the blocking issue (the one that must finish first)

**Do NOT use `addSubIssue`** — that creates parent-child hierarchy, not dependency relationships.

**Fallback** (if `addBlockedBy` fails or is not available): Add a dependency comment to the blocked issue:

```bash
gh issue comment <number> --repo <repo> --body "Depends on #<blocker_number> (detected by daf-issue-topo-sort)"
```

---

## Step 6: Output

Display four outputs to the user:

### Ordered List with Dependency Reasons

```
## Execution Order

1. #949 — "Add config_utils validation" (no dependencies)
2. #1389 — "Refactor MCP server" (no dependencies)
3. #948 — "Update hook_processing" — depends on #949 (explicit)
4. #1251 — "Fix hook edge cases" — depends on #948 (explicit), conflicts with #1364 (hook_processing.py)
5. #1364 — "Hook error handling" — conflicts with #1251 (hook_processing.py)
```

### Concurrent Groups

```
## Concurrent Groups

Group 1 (parallel): #949 config_utils.py, #1389 mcp_server.py, #1388 validators.py
Group 2 (after Group 1): #948 hook_processing.py — depends on #949
Group 3 (after Group 2): #1251 hook_processing.py — depends on #948, conflicts with #1364
Group 4 (after Group 3): #1364 hook_processing.py — conflicts with #1251
```

### Concurrent Development Opportunities

Show which issues from different groups can be developed at the same time to maximize throughput. Two issues can be concurrent if they have no dependency edge AND no conflict edge between them, even if they are in different sequential groups.

```
## Concurrent Development Opportunities

| While working on...       | You can also work on...              | Why safe                          |
|---------------------------|--------------------------------------|-----------------------------------|
| #948 (hook_processing)    | #1389 (mcp_server), #1388 (validators) | No shared files, no dependency |
| #1251 (hook edge cases)   | #1389 (mcp_server)                   | No shared files, no dependency    |
| #1364 (hook errors)       | #1388 (validators)                   | No shared files, no dependency    |
```

This table helps developers with multiple contributors plan parallel work across the timeline, not just within a single group.

### Conflict Matrix

```
## File Conflict Matrix

| File                | Issues          |
|---------------------|-----------------|
| hook_processing.py  | #948, #1251, #1364 |
| config_utils.py     | #949, #952      |
| validators.py       | #1388           |
```

### Save Results

After displaying all outputs, ask the user:

```
Save these results to a markdown file? (yes/no)
```

If yes, ask which directory to save in (suggest current directory as default). Save the full output (execution order, concurrent groups, concurrent development opportunities, conflict matrix, dependency graph, and proposed links) as a markdown file named `issue-topo-sort-<label-or-parent>-<YYYY-MM-DD>.md`.

---

## Edge Cases

- **No issues found**: Report "No open issues found for the given filter" and exit
- **Single issue**: Report it directly, no sorting needed
- **No dependencies or conflicts**: All issues in one parallel group
- **All issues conflict**: Sequential order, one per group
- **External dependencies** (issue depends on something outside the label/parent): Note it but don't include in graph — report as "external dependency on #X (not in scope)"
- **Closed/Done issues referenced as dependencies**: Skip them (dependency already satisfied)

## Performance Notes

- For large issue sets (20+), file analysis is the bottleneck — prioritize grep over deep codebase investigation
- Cache file analysis results within the session (don't re-analyze if re-running)
- For JIRA, batch-fetch issues where possible using JQL rather than individual API calls

# JIRA Backend Integration Rules

**CRITICAL**: ALL JIRA issue descriptions MUST use JIRA Wiki markup, NOT Markdown.

This file provides backend-specific integration rules for working with JIRA. These rules are automatically loaded when you use the JIRA backend in DevAIFlow.

## JIRA Wiki Markup Syntax

JIRA Wiki markup ensures proper rendering in the JIRA UI. Using Markdown syntax will cause formatting issues.

### Syntax Differences

| Element | ❌ Markdown (WRONG) | ✅ JIRA Wiki Markup (CORRECT) |
|---------|---------------------|-------------------------------|
| Header 2 | `## Header` | `h2. Header` |
| Header 3 | `### Header` | `h3. Header` |
| Bold | `**bold**` | `*bold*` |
| Italic | `*italic*` | `_italic_` |
| Code block | ` ```bash\ncode\n``` ` | `{code:bash}\ncode\n{code}` |
| Inline code | `` `code` `` | `{{code}}` |
| Unordered list | `- item` | `* item` |
| Ordered list | `1. item` | `# item` |
| Link | `[text](url)` | `[text|url]` |

### Common Mistakes to Avoid

❌ **WRONG (Markdown):**
```
## Problem Description

This is **important** and uses `code` examples.

### Steps
1. First step
2. Second step

```bash
run command
```
```

✅ **CORRECT (JIRA Wiki Markup):**
```
h2. Problem Description

This is *important* and uses {{code}} examples.

h3. Steps
# First step
# Second step

{code:bash}
run command
{code}
```

## When to Use JIRA Wiki Markup

- ✅ JIRA issue descriptions
- ✅ JIRA comments
- ✅ JIRA acceptance criteria
- ✅ Any text field that will be displayed in JIRA
- ❌ NOT in documentation files (.md files in repositories)
- ❌ NOT in README.md or other project documentation

## Complete Reference

See DAF_AGENTS.md for the complete JIRA Wiki markup reference and additional JIRA integration guidelines.

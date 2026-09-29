"""AI-powered PR/MR template parsing and filling."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console

from devflow.config.loader import ConfigLoader
from devflow.utils import strip_code_fences
from devflow.utils.backend_detection import get_issue_tracker_backend

console = Console()


def _markdown_sections(lines: List[str]) -> List[Tuple[int, int, int, str]]:
    """Return direct markdown section ranges for a list of lines."""
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    headings = []
    fenced = False
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = heading_re.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    return [
        (start, headings[position + 1][0] if position + 1 < len(headings) else len(lines), level, title)
        for position, (start, level, title) in enumerate(headings)
    ]


def _has_meaningful_section_content(lines: List[str]) -> bool:
    """Return whether section lines contain content instead of template guidance."""
    content = re.sub(r"<!--.*?-->", "", "\n".join(lines), flags=re.DOTALL)
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        if re.match(r"^[-*+]\s+\[[ xX]\]\s+", stripped):
            continue
        if re.match(r"(?i)^(?:assisted-by|co-authored-by)\s*:", stripped):
            continue
        if stripped == "..." or stripped.startswith("# Record command"):
            continue
        if re.match(
            r"(?i)^(?:select|choose|describe|summarize|link|list|record|include|enter|if applicable)\b",
            stripped,
        ):
            continue
        if re.fullmatch(r"<(?:PROJ|JIRA|ISSUE)-[^>]+>", stripped, flags=re.IGNORECASE):
            continue
        return True
    return False


def _command_context(git_context: dict) -> List[Tuple[str, Optional[int]]]:
    """Normalize captured command data for template rendering."""
    commands = git_context.get("commands_run") or git_context.get("test_commands") or []
    if isinstance(commands, str):
        commands = [commands]

    normalized = []
    for item in commands:
        if isinstance(item, dict):
            command = item.get("command")
            exit_code = item.get("exit_code")
        else:
            command = getattr(item, "command", item)
            exit_code = getattr(item, "exit_code", None)
        if command:
            normalized.append((str(command), exit_code))
    return normalized


def _template_needs_fallback(template_content: str, filled_content: str) -> bool:
    """Detect AI output that still resembles an unpopulated template."""
    if not filled_content.strip():
        return True

    # Preserve the historical contract for callers that use this helper with a
    # short, already-generated response instead of a complete markdown body.
    if not re.search(r"^\s*#{1,6}\s+", filled_content, flags=re.MULTILINE):
        return False

    if re.search(r"<!--.*?-->", filled_content, flags=re.DOTALL):
        return True

    if re.search(
        r"(?i)PROJ-NNNN|JIRA-KEY|<name of code assistant>|# Record command evidence|^\s*(?:select exactly one|include relevant)\b|^\s*\.\.\.\s*$",
        filled_content,
        flags=re.MULTILINE,
    ):
        return True

    template_lines = template_content.splitlines()
    filled_lines = filled_content.splitlines()
    template_sections = _markdown_sections(template_lines)
    filled_sections = _markdown_sections(filled_lines)
    filled_titles = {(level, title.lower()) for _, _, level, title in filled_sections}

    for start, end, level, title in template_sections:
        if (level, title.lower()) not in filled_titles:
            return True

        matching = [
            (filled_start, filled_end)
            for filled_start, filled_end, filled_level, filled_title in filled_sections
            if filled_level == level and filled_title.lower() == title.lower()
        ]
        if not matching:
            return True
        filled_start, filled_end = matching[0]
        template_body = template_lines[start + 1:end]
        filled_body = filled_lines[filled_start + 1:filled_end]

        if not _has_meaningful_section_content(template_body) and not _has_meaningful_section_content(filled_body):
            return True

        template_checkboxes = re.findall(r"^\s*[-*+]\s+\[\s\]\s+(.+)$", "\n".join(template_body), re.MULTILINE)
        if template_checkboxes:
            filled_text = "\n".join(filled_body)
            unchanged = all(label.strip() in filled_text for label in template_checkboxes)
            has_checked_item = bool(re.search(r"^\s*[-*+]\s+\[[xX]\]", filled_text, re.MULTILINE))
            has_explicit_status = bool(re.search(r"(?i)not (?:verified|captured|required)|not applicable", filled_text))
            if unchanged and not has_checked_item and not has_explicit_status:
                return True

    return False


def _finalize_ai_template(
    template_content: str,
    result: str,
    session,
    git_context: dict,
    jira_url: Optional[str],
    agent_display_name: str,
) -> str:
    """Validate AI output and use the deterministic filler for skeletons."""
    filled_template = strip_code_fences(result)
    if _template_needs_fallback(template_content, filled_template):
        console.print("[yellow]⚠[/yellow] AI returned an incomplete template, using deterministic filling")
        return _fill_template_fallback(
            template_content,
            session,
            git_context,
            jira_url=jira_url,
            agent_display_name=agent_display_name,
        )
    return filled_template


def fill_pr_template_with_ai(
    template_content: str,
    session,
    working_dir: Path,
    git_context: dict,
    display_name: Optional[str] = None,
) -> str:
    """Fill PR/MR template using AI to understand and populate fields.

    This function uses AI to:
    1. Parse the template to understand what information each section needs
    2. Analyze git context (commits, changes, branch) and session data
    3. Intelligently fill each section based on the template's requirements

    Args:
        template_content: Raw template content from GitHub/GitLab
        session: Session object with issue key, goal, etc.
        working_dir: Working directory for git analysis
        git_context: Dictionary containing git information:
            - commit_log: Recent commit messages
            - changed_files: List of changed files
            - base_branch: Base branch name
            - current_branch: Current branch name
            - commands_run: Captured commands and exit codes, when available

    Returns:
        Filled template ready for PR/MR creation
    """
    # Build comprehensive context for AI
    context_parts = []

    # Load JIRA URL from config
    config_loader = ConfigLoader()
    config = config_loader.load_config() if config_loader.config_file.exists() else None
    jira_url = config.jira.url if config and config.jira else None

    # Resolve agent name for Assisted-by field
    from devflow.agent.factory import get_agent_display_name, resolve_agent_backend
    _agent_backend = resolve_agent_backend(config=config, session=session)
    _agent_display = get_agent_display_name(_agent_backend)
    from devflow.utils.model_provider import get_active_profile
    model_profile = get_active_profile(
        config,
        override_profile_name=getattr(session, "model_profile", None),
        agent_backend=_agent_backend,
        command="pr_template",
        utility=True,
    ) if config else None
    context_parts.append(f"AI Assistant: {_agent_display}")

    # Detect issue tracker backend
    issue_tracker = get_issue_tracker_backend(session)

    # Session context — build issue URL based on backend
    if session.issue_key:
        if issue_tracker == "github":
            context_parts.append(f"GitHub Issue: {session.issue_key}")
        elif issue_tracker == "gitlab":
            context_parts.append(f"GitLab Issue: {session.issue_key}")
        else:
            context_parts.append(f"JIRA Issue: {session.issue_key}")
            if jira_url:
                jira_base = jira_url.rstrip('/')
                context_parts.append(f"JIRA URL: {jira_base}/browse/{session.issue_key}")

    context_parts.append(f"Session Goal: {session.goal}")
    issue_metadata = getattr(session, "issue_metadata", None)
    if isinstance(issue_metadata, dict):
        if issue_metadata.get("summary"):
            context_parts.append(f"Issue Summary: {issue_metadata['summary']}")
        if issue_metadata.get("description"):
            context_parts.append(f"Issue Description: {issue_metadata['description']}")

    # Get branch from active conversation
    active_conv = session.active_conversation
    if active_conv and active_conv.branch:
        context_parts.append(f"Branch: {active_conv.branch}")

    # Git context
    if git_context.get('commit_log'):
        context_parts.append(f"\nCommit History:\n{git_context['commit_log']}")

    if git_context.get('changed_files'):
        files_str = "\n".join(git_context['changed_files'][:30])
        total_files = len(git_context['changed_files'])
        context_parts.append(f"\nFiles Changed ({total_files}):\n{files_str}")
        if total_files > 30:
            context_parts.append(f"... and {total_files - 30} more files")

    if git_context.get('base_branch'):
        context_parts.append(f"\nBase Branch: {git_context['base_branch']}")

    commands_run = _command_context(git_context)
    if commands_run:
        command_lines = "\n".join(command for command, _ in commands_run[:10])
        context_parts.append(f"\nCommands Run:\n{command_lines}")

    context = "\n".join(context_parts)

    # Build prompt for AI
    prompt = f"""You are helping to create a pull request. You have been given a PR template and context about the changes.

Your task is to fill in the template by:
1. Reading the template carefully to understand what each section asks for
2. Using the provided context (commits, files changed, JIRA info, session goal) to populate each section
3. Preserving the template structure and markdown formatting
4. Replacing placeholder comments and example text with actual content
5. Being specific and technical in your descriptions

**PR Template:**
```
{template_content}
```

**Context about the changes:**
```
{context}
```

**Instructions:**
- Read each section's HTML comments (<!-- ... -->) to understand what information is needed
- Replace placeholder patterns like "PROJ-NNNN", "JIRA-KEY", etc. with actual values
- Fill in the Description/Summary section based on commits and changes
- For "Assisted-by" fields, use the AI assistant name from the context
- For "Steps to test" sections, generate specific testing steps based on the changes
- For "Deployment considerations", analyze if changes need special deployment handling
- For checkbox sections, select evidence-supported options and explicitly mark unknown or inapplicable items instead of leaving the template defaults
- For command or testing evidence, use the captured commands when available; otherwise state that the evidence was not captured
- Preserve all markdown formatting (headers, lists, checkboxes, etc.)
- Remove or replace instructional comments with actual content
- Do NOT add any extra sections or content not in the template
- Return ONLY the filled template, nothing else

Generate the filled PR/MR description now:"""

    try:
        from devflow.agent import create_agent_client
        from devflow.agent.factory import resolve_agent_backend
        agent_backend = resolve_agent_backend(config=config, session=session)
        agent = create_agent_client(agent_backend)
        result = agent.generate_text(
            prompt,
            timeout=45,
            display_name=display_name,
            config=config,
            model_provider_profile=model_profile,
        )
        if result:
            filled_template = _finalize_ai_template(
                template_content,
                result,
                session,
                git_context,
                jira_url,
                _agent_display,
            )
            console.print(f"[dim]✓ Template filled using AI ({agent.get_agent_name()})[/dim]")
            return filled_template

        # Agent CLI failed: try Anthropic API
        console.print("[dim]Agent CLI failed, trying Anthropic API...[/dim]")
        api_result = _fill_template_with_api(prompt, profile=model_profile)
        return _finalize_ai_template(
            template_content,
            api_result,
            session,
            git_context,
            jira_url,
            _agent_display,
        )

    except FileNotFoundError:
        console.print("[dim]Agent CLI not found, trying Anthropic API...[/dim]")
        api_result = _fill_template_with_api(prompt, profile=model_profile)
        return _finalize_ai_template(
            template_content,
            api_result,
            session,
            git_context,
            jira_url,
            _agent_display,
        )
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠[/yellow] AI template filling timed out, using fallback")
        return _fill_template_fallback(template_content, session, git_context, jira_url=jira_url, agent_display_name=_agent_display)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] AI template filling failed: {e}")
        return _fill_template_fallback(template_content, session, git_context, jira_url=jira_url, agent_display_name=_agent_display)


def _fill_template_with_api(prompt: str, profile: Optional[dict] = None) -> str:
    """Fill template using Anthropic API as fallback.

    Args:
        prompt: Pre-built prompt string

    Returns:
        Filled template or raises exception
    """
    try:
        import anthropic
        import os

        api_key = (profile or {}).get("api_key") or (profile or {}).get("auth_token") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client_kwargs = {"api_key": api_key}
        api_url = (profile or {}).get("api_url") or (profile or {}).get("base_url")
        if api_url:
            client_kwargs["base_url"] = api_url
        client = anthropic.Anthropic(**client_kwargs)

        from devflow.utils.model_provider import get_model_name_from_profile
        model = get_model_name_from_profile(profile, command="pr_template", utility=True) or "claude-haiku-4-5-20251001"

        message = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        if message.content and len(message.content) > 0:
            filled_template = message.content[0].text.strip()

            filled_template = strip_code_fences(filled_template)

            console.print("[dim]✓ Template filled using AI (Anthropic API)[/dim]")
            return filled_template

        raise RuntimeError("No content in API response")

    except Exception as e:
        raise RuntimeError(f"API template filling failed: {e}")


def _fill_template_fallback(
    template_content: str,
    session,
    git_context: dict,
    jira_url: Optional[str] = None,
    agent_display_name: str = "Claude",
) -> str:
    """Fill arbitrary markdown PR templates without leaving a skeleton.

    The fallback treats headings, checkbox groups, code fences, and instructional
    comments as a lightweight template schema. It intentionally reports missing
    evidence instead of claiming that tests or manual checks were performed.
    """
    console.print("[dim]Using fallback template filling (no AI)[/dim]")

    if jira_url is None:
        config_loader = ConfigLoader()
        config = config_loader.load_config() if config_loader.config_file.exists() else None
        jira_url = config.jira.url if config and config.jira else None

    issue_tracker = get_issue_tracker_backend(session)
    issue_key = getattr(session, "issue_key", None)
    issue_key = str(issue_key) if issue_key else None
    goal = str(getattr(session, "goal", "") or "").strip()
    issue_metadata = getattr(session, "issue_metadata", None)
    issue_summary = ""
    issue_description = ""
    if isinstance(issue_metadata, dict):
        issue_summary = str(issue_metadata.get("summary") or "").strip()
        issue_description = str(issue_metadata.get("description") or "").strip()
    changed_files = [str(path) for path in (git_context.get("changed_files") or [])]
    commands = _command_context(git_context)
    commit_lines = [
        line.strip().lstrip("-* ")
        for line in str(git_context.get("commit_log") or "").splitlines()
        if line.strip()
    ]
    context_text = " ".join([goal, issue_summary, issue_description, *commit_lines, *changed_files]).lower()

    if issue_key:
        filled = re.sub(
            r"(?:PROJ|JIRA|ISSUE)-(?:NNNN|KEY|\d+)",
            lambda _: issue_key,
            template_content,
            flags=re.IGNORECASE,
        )
    else:
        filled = template_content
        filled = re.sub(
            r"(?im)^\s*(?:Jira|GitHub|GitLab) Issue:\s*<[^>]*>\s*$",
            "Issue: N/A",
            filled,
        )

    issue_url = None
    if issue_key and issue_tracker == "jira" and jira_url:
        issue_url = f"{jira_url.rstrip('/')}/browse/{issue_key}"
    elif issue_key and issue_tracker in {"github", "gitlab"} and "#" in issue_key:
        repo_path, issue_number = issue_key.rsplit("#", 1)
        if repo_path and issue_number.isdigit():
            host = "github.com" if issue_tracker == "github" else "gitlab.com"
            issue_path = "issues" if issue_tracker == "github" else "-/issues"
            issue_url = f"https://{host}/{repo_path}/{issue_path}/{issue_number}"

    if issue_url:
        filled = re.sub(
            r"(Jira Issue:\s*)<[^>\n]*>",
            lambda match: f"{match.group(1)}<{issue_url}>",
            filled,
            flags=re.IGNORECASE,
        )

    issue_reference = "N/A"
    if issue_key:
        if issue_url and issue_tracker == "jira":
            issue_reference = f"Jira Issue: <{issue_url}>"
        elif issue_url:
            issue_reference = f"Closes {issue_key} ([issue]({issue_url}))"
        else:
            issue_reference = f"Issue: {issue_key}"

    description_lines = [goal or issue_summary or "No session goal was recorded."]
    if issue_summary and issue_summary not in description_lines[0]:
        description_lines.append(f"Issue summary: {issue_summary}")
    if commit_lines:
        description_lines.extend(["", "Changes in this branch:"])
        description_lines.extend(f"- {line}" for line in commit_lines[:5])

    test_files = [
        path for path in changed_files
        if re.search(r"(^|/)(tests?|specs?)(/|$)|(^|/)test_[^/]+|_test\.", path, re.IGNORECASE)
    ]
    test_commands = [
        (command, exit_code)
        for command, exit_code in commands
        if re.search(r"\b(pytest|unittest|npm\s+test|yarn\s+test|pnpm\s+test|cargo\s+test|go\s+test|mvn\s+test|gradle\s+test)\b", command, re.IGNORECASE)
    ]
    tests_passed = bool(test_commands) and all(
        exit_code == 0 for _, exit_code in test_commands
    )

    security_change = bool(
        re.search(r"security|vulnerab|exploit|cve|threat|credential|secret|permission|detection", context_text)
    )
    if security_change:
        security_detail = "Security behavior is implicated by the session context; review the threat and user-visible impact before merging."
        change_type = "Security fix or detection change"
    elif re.search(r"documentation|docs?|readme|workflow", context_text):
        security_detail = "No security behavior change was identified from the session context."
        change_type = "Documentation or workflow change"
    elif re.search(r"bug|fix|defect|regression|error|failure|broken|repair", context_text):
        security_detail = "No security behavior change was identified from the session context."
        change_type = "Bug fix"
    elif re.search(r"refactor|maintenance|cleanup", context_text):
        security_detail = "No security behavior change was identified from the session context."
        change_type = "Refactoring or maintenance"
    else:
        security_detail = "No security behavior change was identified from the session context."
        change_type = "New feature"

    security_keywords = ("security", "affects", "threat", "protection", "behavior", "impact")
    no_security_keywords = ("no security", "no impact", "unaffected", "none")

    def update_sections(predicate, updater) -> None:
        nonlocal lines
        for start, end, level, title in reversed(_markdown_sections(lines)):
            if predicate(title, level):
                lines[start + 1:end] = updater(lines[start + 1:end], title)

    checkbox_re = re.compile(r"^(\s*[-*+]\s+)\[([ xX])\](\s+.*)$")

    def checkbox_lines(body: List[str]) -> List[Tuple[int, str, re.Match]]:
        matches = []
        for index, line in enumerate(body):
            match = checkbox_re.match(line)
            if match:
                matches.append((index, match.group(3).strip(), match))
        return matches

    def select_checkbox(body: List[str], keywords: Tuple[str, ...]) -> List[str]:
        matches = checkbox_lines(body)
        if not matches or any(match.group(2).lower() == "x" for _, _, match in matches):
            return body
        selected = next(
            (index for index, label, _ in matches if any(keyword in label.lower() for keyword in keywords)),
            matches[0][0],
        )
        match = checkbox_re.match(body[selected])
        if match:
            body[selected] = f"{match.group(1)}[x]{match.group(3)}"
        return body

    def annotate_checkbox(body: List[str], index: int, match, note: str) -> None:
        if match.group(2).lower() == "x" or note.lower() in body[index].lower():
            return
        body[index] = f"{body[index].rstrip()} ({note})"

    def update_issue(body: List[str], _title: str) -> List[str]:
        if _has_meaningful_section_content(body):
            return body
        return [issue_reference]

    def update_description(body: List[str], _title: str) -> List[str]:
        if _has_meaningful_section_content(body):
            return body
        attribution_lines = [
            line for line in body
            if re.match(r"(?i)^\s*(?:Assisted-by|Co-Authored-By)\s*:", line)
        ]
        return description_lines + ([""] + attribution_lines if attribution_lines else [])

    def update_change_type(body: List[str], _title: str) -> List[str]:
        if checkbox_lines(body):
            return select_checkbox(body, tuple(change_type.lower().split()))
        return body if _has_meaningful_section_content(body) else [f"Change classification: {change_type}"]

    def update_security(body: List[str], _title: str) -> List[str]:
        matches = checkbox_lines(body)
        if matches:
            if not any(match.group(2).lower() == "x" for _, _, match in matches):
                keywords = security_keywords if security_change else no_security_keywords
                body = select_checkbox(body, keywords)
            if not _has_meaningful_section_content(body):
                body.extend(["", security_detail])
            return body
        return body if _has_meaningful_section_content(body) else [security_detail]

    def update_testing(body: List[str], _title: str) -> List[str]:
        if any(re.match(r"^\s*\d+\.\s+(?:Pull down the PR|\.\.\.)\s*$", line, re.IGNORECASE) for line in body):
            return [
                "1. Pull down the PR and verify the changes build successfully.",
                "2. Review the changed files for correctness.",
                "3. Run the project's test suite.",
            ]

        updated = []
        for line in body:
            match = checkbox_re.match(line)
            if not match:
                updated.append(line)
                continue
            label = match.group(3).lower()
            index = len(updated)
            updated.append(line)
            if "test" in label and ("added" in label or "updated" in label):
                if test_files:
                    updated[index] = f"{match.group(1)}[x]{match.group(3)}"
                else:
                    annotate_checkbox(updated, index, match, "test changes not evidenced in session context")
            elif "test" in label and ("pass" in label or "locally" in label):
                if tests_passed:
                    updated[index] = f"{match.group(1)}[x]{match.group(3)}"
                else:
                    annotate_checkbox(updated, index, match, "test results not captured in session context")
            elif "manual" in label or "verification" in label:
                annotate_checkbox(updated, index, match, "manual verification not captured in session context")
            else:
                annotate_checkbox(updated, index, match, "status not captured in session context")

        if not _has_meaningful_section_content(updated):
            evidence = ["", "Evidence from session context:"]
            if test_files:
                evidence.append(f"- Test files changed: {', '.join(f'`{path}`' for path in test_files[:10])}")
            else:
                evidence.append("- No test files were identified among the changed files.")
            if test_commands:
                evidence.append(f"- Test commands captured: {', '.join(f'`{command}`' for command, _ in test_commands)}")
            else:
                evidence.append("- Test command results were not captured in the session metadata.")
            updated.extend(evidence)
        return updated

    def update_commands(body: List[str], _title: str) -> List[str]:
        command_lines = []
        for command, exit_code in commands:
            suffix = f" (exit code: {exit_code})" if exit_code is not None else ""
            command_lines.append(f"{command}{suffix}")
        if not command_lines:
            command_lines = ["No command evidence was captured in the session context."]

        fence_indexes = [index for index, line in enumerate(body) if line.strip().startswith("```")]
        if len(fence_indexes) >= 2:
            first, second = fence_indexes[0], fence_indexes[1]
            return body[:first + 1] + command_lines + body[second:]
        if _has_meaningful_section_content(body):
            return body + ["", "```text", *command_lines, "```"]
        return ["```text", *command_lines, "```"]

    def checklist_note(label: str) -> Optional[str]:
        lower = label.lower()
        if "documentation" in lower:
            return None if any(path.lower().endswith((".md", ".rst")) or "/docs/" in path.lower() for path in changed_files) else "not required for this change"
        if "changelog" in lower:
            return None if any("changelog" in path.lower() for path in changed_files) else "no changelog update identified"
        if "dependenc" in lower:
            return None if any(Path(path).name.lower() in {"pyproject.toml", "setup.py", "requirements.txt", "package.json"} for path in changed_files) else "no new dependencies identified"
        if "security" in lower and not security_change:
            return "not applicable to this change"
        if "test" in lower and test_files:
            return None
        if "limited" in lower and changed_files:
            return None
        return "not independently verified in session context"

    def update_checklist(body: List[str], _title: str) -> List[str]:
        updated = []
        for line in body:
            match = checkbox_re.match(line)
            if not match:
                updated.append(line)
                continue
            label = match.group(3).strip()
            note = checklist_note(label)
            if match.group(2).lower() == "x" or note is None:
                if match.group(2).lower() == " " and note is None:
                    updated.append(f"{match.group(1)}[x]{match.group(3)}")
                else:
                    updated.append(line)
            else:
                index = len(updated)
                updated.append(line)
                annotate_checkbox(updated, index, match, note)
        return updated

    lines = filled.splitlines()
    update_sections(
        lambda title, level: level <= 2 and bool(re.search(r"\b(issue|ticket|tracking|jira|github|gitlab)\b", title, re.IGNORECASE)),
        update_issue,
    )
    update_sections(
        lambda title, level: level <= 2 and bool(re.search(r"\b(description|summary|overview|what changed)\b", title, re.IGNORECASE)),
        update_description,
    )
    update_sections(
        lambda title, level: level <= 2 and bool(re.search(r"type of change|change type|classification|category", title, re.IGNORECASE)),
        update_change_type,
    )
    update_sections(
        lambda title, level: level <= 2 and "security" in title.lower(),
        update_security,
    )
    update_sections(
        lambda title, level: level <= 3 and bool(re.search(r"\b(test|testing|verification|validation|steps to test)\b", title, re.IGNORECASE)),
        update_testing,
    )
    update_sections(
        lambda title, level: level <= 2 and "command" in title.lower(),
        update_commands,
    )
    update_sections(
        lambda title, level: level <= 2 and "checklist" in title.lower(),
        update_checklist,
    )

    filled = "\n".join(lines)
    filled = re.sub(
        r"(?im)^(\s*(?:Assisted-by|Co-Authored-By)\s*:\s*)(.*)$",
        lambda match: (
            f"{match.group(1)}{agent_display_name}"
            if not match.group(2).strip()
            or re.search(r"(?i)<|who helped|name of code assistant|\.\.\.|<!--", match.group(2))
            else match.group(0)
        ),
        filled,
    )
    filled = re.sub(r"<!--.*?-->", "", filled, flags=re.DOTALL)
    filled = re.sub(
        r"(?im)^\s*(?:select|choose|include|record)\b.*(?:option|below|detail|evidence|command|applicable).*?$\n?",
        "",
        filled,
    )
    filled = re.sub(
        r"(?m)^\s*\.\.\.\s*$",
        "N/A - no additional details were captured in the session context.",
        filled,
    )

    lines = filled.splitlines()
    for start, end, _level, _title in reversed(_markdown_sections(lines)):
        body = lines[start + 1:end]
        if any(re.match(r"(?i)^\s*(?:Assisted-by|Co-Authored-By)\s*:", line) for line in body):
            continue
        if _has_meaningful_section_content(body):
            continue
        if checkbox_lines(body):
            if any(
                match.group(2).lower() == "x"
                or re.search(r"(?i)not (?:verified|captured|required)|not applicable|no .* identified", match.group(3))
                for _, _, match in checkbox_lines(body)
            ):
                continue
            lines[start + 1:end] = body + ["", "Checkbox status was not captured in the session context."]
        else:
            lines[start + 1:end] = ["N/A - No applicable information was captured in the session context."]

    return "\n".join(lines).strip() + "\n"

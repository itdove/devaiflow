"""AI-powered PR/MR template parsing and filling."""

import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from devflow.config.loader import ConfigLoader

console = Console()


def fill_pr_template_with_ai(
    template_content: str,
    session,
    working_dir: Path,
    git_context: dict
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

    Returns:
        Filled template ready for PR/MR creation
    """
    try:
        # Build comprehensive context for AI
        context_parts = []

        # Load JIRA URL from config
        config_loader = ConfigLoader()
        config = config_loader.load_config() if config_loader.config_file.exists() else None
        jira_url = config.jira.url if config and config.jira else None

        # Session context
        if session.issue_key:
            context_parts.append(f"JIRA Issue: {session.issue_key}")
            if jira_url:
                context_parts.append(f"JIRA URL: {jira_url}/browse/{session.issue_key}")

        context_parts.append(f"Session Goal: {session.goal}")

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
- For "Assisted-by" fields, use: Claude
- For "Steps to test" sections, generate specific testing steps based on the changes
- For "Deployment considerations", analyze if changes need special deployment handling
- Preserve all markdown formatting (headers, lists, checkboxes, etc.)
- Remove or replace instructional comments with actual content
- Do NOT add any extra sections or content not in the template
- Return ONLY the filled template, nothing else

Generate the filled PR/MR description now:"""

        # Try Claude CLI first (faster, better)
        result = subprocess.run(
            ["claude"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=45,
        )

        if result.returncode == 0:
            filled_template = result.stdout.strip()

            # Clean up any code fences if AI added them
            if filled_template.startswith('```'):
                lines = filled_template.split('\n')
                # Remove first and last line if they're code fences
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith('```'):
                    lines = lines[:-1]
                filled_template = '\n'.join(lines).strip()

            console.print("[dim]✓ Template filled using AI (Claude CLI)[/dim]")
            return filled_template

        # Fallback to Anthropic API if Claude CLI not available
        console.print("[dim]Claude CLI not available, trying Anthropic API...[/dim]")
        return _fill_template_with_api(template_content, context)

    except FileNotFoundError:
        # Claude CLI not installed, try API
        console.print("[dim]Claude CLI not found, trying Anthropic API...[/dim]")
        return _fill_template_with_api(template_content, context)
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠[/yellow] AI template filling timed out, using fallback")
        return _fill_template_fallback(template_content, session, git_context)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] AI template filling failed: {e}")
        return _fill_template_fallback(template_content, session, git_context)


def _fill_template_with_api(template_content: str, context: str) -> str:
    """Fill template using Anthropic API as fallback.

    Args:
        template_content: Raw template content
        context: Formatted context string

    Returns:
        Filled template or raises exception
    """
    try:
        import anthropic
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)

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
- For "Assisted-by" fields, use: Claude
- For "Steps to test" sections, generate specific testing steps based on the changes
- For "Deployment considerations", analyze if changes need special deployment handling
- Preserve all markdown formatting (headers, lists, checkboxes, etc.)
- Remove or replace instructional comments with actual content
- Do NOT add any extra sections or content not in the template
- Return ONLY the filled template, nothing else

Generate the filled PR/MR description now:"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        if message.content and len(message.content) > 0:
            filled_template = message.content[0].text.strip()

            # Clean up code fences if present
            if filled_template.startswith('```'):
                lines = filled_template.split('\n')
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith('```'):
                    lines = lines[:-1]
                filled_template = '\n'.join(lines).strip()

            console.print("[dim]✓ Template filled using AI (Anthropic API)[/dim]")
            return filled_template

        raise RuntimeError("No content in API response")

    except Exception as e:
        raise RuntimeError(f"API template filling failed: {e}")


def _fill_template_fallback(template_content: str, session, git_context: dict) -> str:
    """Simple fallback template filling when AI is not available.

    Uses basic pattern matching as a last resort.

    Args:
        template_content: Raw template content
        session: Session object
        git_context: Git context dictionary

    Returns:
        Filled template with basic substitutions
    """
    import re

    console.print("[dim]Using fallback template filling (no AI)[/dim]")

    # Load JIRA URL from config
    config_loader = ConfigLoader()
    config = config_loader.load_config() if config_loader.config_file.exists() else None
    jira_url = config.jira.url if config and config.jira else None

    filled = template_content

    # Replace issue tracker placeholders (e.g., PROJ-NNNN, JIRA-KEY, ISSUE-123)
    if session.issue_key:
        filled = re.sub(
            r'(?:PROJ|JIRA|ISSUE)-(?:NNNN|\w+)',
            session.issue_key,
            filled,
            flags=re.IGNORECASE
        )
        if jira_url:
            filled = re.sub(
                r'(Jira Issue:\s*)<[^>]*>',
                f'\\1<{jira_url}/browse/{session.issue_key}>',
                filled,
                flags=re.IGNORECASE
            )

    # Fill in basic description from session goal
    description_pattern = r'(## Description\s*\n)(?:<!--.*?-->\s*\n)?'
    filled = re.sub(
        description_pattern,
        f'\\1{session.goal}\n\nAssisted-by: Claude\n\n',
        filled,
        flags=re.DOTALL
    )

    return filled

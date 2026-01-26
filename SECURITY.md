# Security Policy

## Reporting Security Vulnerabilities

We take the security of DevAIFlow seriously. If you discover a security vulnerability, please follow these steps:

### 1. Do Not Disclose Publicly

Please **do not** create a public GitHub issue for security vulnerabilities. Public disclosure before a fix is available puts all users at risk.

### 2. Report Privately

Report security vulnerabilities through one of these channels:

- **GitHub Security Advisories**: Use the [GitHub Security Advisory](https://github.com/itdove/devaiflow/security/advisories/new) feature (preferred)
- **Email**: Send details to the project maintainers (see contact information below)

### 3. Include Details

When reporting a vulnerability, please include:

- **Description**: Clear description of the vulnerability
- **Impact**: What an attacker could do with this vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Affected Versions**: Which versions of DevAIFlow are affected
- **Suggested Fix**: If you have ideas for fixing the issue (optional)
- **Your Contact Information**: How we can reach you for follow-up questions

### Example Report

```
Title: Potential command injection in session name handling

Description:
User-provided session names are passed directly to shell commands without
proper sanitization, allowing command injection.

Impact:
An attacker could execute arbitrary commands on the user's system by
creating a session with a malicious name.

Steps to Reproduce:
1. Run: daf new --name "test; rm -rf /tmp/test"
2. Observe that the command after semicolon is executed

Affected Versions:
- v0.1.0 and earlier

Suggested Fix:
Use shlex.quote() to properly escape session names before passing to shell.
```

## Response Timeline

We will:

1. **Acknowledge** receipt of your report within **48 hours**
2. **Investigate** and confirm the vulnerability
3. **Develop** a fix in a private branch
4. **Notify you** when a fix is ready for testing
5. **Release** a security update with credit to the reporter (if desired)
6. **Publish** a security advisory after the fix is released

Typical timeline: **2-4 weeks** from report to public disclosure (depending on severity and complexity).

## Security Best Practices

When using DevAIFlow:

### 1. Protect Your Credentials

- **Never commit** JIRA API tokens to git repositories
- Use environment variables for sensitive configuration:
  ```bash
  export JIRA_API_TOKEN="your-token"
  export GITHUB_TOKEN="your-token"
  ```
- Add `.env` files to `.gitignore` if using them

### 2. Review Session Exports

Before sharing session exports with teammates:

- Check for accidentally included credentials or sensitive data
- Review conversation history for confidential information
- Session exports include full conversation history - sanitize if needed

### 3. Validate JIRA URLs

- Ensure your `JIRA_URL` configuration points to your legitimate JIRA instance
- Verify SSL certificates are valid (don't use `--insecure` curl flags)

### 4. Keep Software Updated

- Regularly update DevAIFlow: `pip install --upgrade --force-reinstall .`
- Subscribe to GitHub releases for security notifications
- Review CHANGELOG.md for security-related updates

### 5. File Permissions

DevAIFlow stores session data in:
- `$DEVAIFLOW_HOME/` - Session metadata and configuration
- `~/.claude/projects/` - Claude Code conversation files

Ensure these directories have appropriate permissions:
```bash
chmod 700 $DEVAIFLOW_HOME
chmod 700 ~/.claude
```

## Known Security Considerations

### 1. Local Data Storage

- Session data (including JIRA keys, conversation history) is stored unencrypted in `$DEVAIFLOW_HOME/`
- Conversation files are stored in `~/.claude/projects/`
- **Mitigation**: Use full-disk encryption and appropriate file permissions

### 2. API Token Handling

- API tokens are read from environment variables
- Tokens are used in HTTP requests to JIRA/GitHub/GitLab
- **Mitigation**: Tokens are not logged or stored by DevAIFlow; use secure token storage solutions for your environment

### 3. Command Injection Risks

- Session names and JIRA keys are used in git commands and file paths
- Input validation is performed, but shell operations carry inherent risks
- **Mitigation**: Avoid special characters in session names; use JIRA key format validation

### 4. Session Export/Import

- Exported session files contain full conversation history
- Files are not encrypted during export
- **Mitigation**: Review exports before sharing; use secure channels for transmission

## Supported Versions

We provide security updates for:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

Older versions may receive critical security fixes on a case-by-case basis.

## Security Contact

- **GitHub**: [@itdove](https://github.com/itdove)
- **Security Advisories**: https://github.com/itdove/devaiflow/security/advisories

## Acknowledgments

We appreciate security researchers who responsibly disclose vulnerabilities. Contributors will be credited in:

- Security advisory
- CHANGELOG.md
- GitHub release notes (if desired)

## Hall of Fame

Thank you to these security researchers who have helped improve DevAIFlow:

- *No vulnerabilities reported yet*

---

**Remember**: When in doubt about whether something is a security issue, please report it privately. We'd rather investigate a false positive than miss a real vulnerability.

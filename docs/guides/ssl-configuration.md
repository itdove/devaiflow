# SSL Certificate Verification Configuration

DevAIFlow supports custom SSL certificate verification for all HTTP requests, including:
- Hierarchical config file downloads (from internal GitLab/GitHub)
- JIRA API requests
- PyPI update checks
- GitHub/GitLab template fetching

## Configuration Options

### Option 1: Environment Variable (Temporary)

Quick override for testing or one-time use:

```bash
# Use system certificates (default - SECURE)
export DAF_SSL_VERIFY=true
daf upgrade

# Disable SSL verification (INSECURE - testing only)
export DAF_SSL_VERIFY=false
daf upgrade

# Use custom CA bundle (RECOMMENDED for internal CAs)
export DAF_SSL_VERIFY=/etc/pki/ca-trust/source/anchors/company-ca.crt
daf upgrade
```

### Option 2: Configuration File (Persistent)

Add to `organization.json` for persistent configuration:

```json
{
  "hierarchical_config_source": "https://gitlab.internal.company.com/org/devaiflow-config/configs",
  "http_client": {
    "ssl_verify": "/etc/pki/ca-trust/source/anchors/company-ca.crt",
    "timeout": 30
  }
}
```

**Configuration fields:**

- `ssl_verify`:
  - `true` (default) - Verify using system certificates
  - `false` - Disable verification (INSECURE)
  - `"/path/to/ca-bundle.crt"` - Use custom CA bundle
- `timeout`: Request timeout in seconds (default: 10)

## Security Warnings

### ⚠️ NEVER use `ssl_verify: false` in production

Disabling SSL verification exposes you to:
- Man-in-the-middle (MITM) attacks
- Credential theft
- Data interception
- Malicious code injection

**Only use `ssl_verify: false` for:**
- Local development with self-signed certificates
- Isolated testing environments
- Temporary troubleshooting (then fix the root cause)

### ✅ Recommended Production Setup

For internal certificate authorities:

1. **Obtain your organization's CA bundle:**
   ```bash
   # Red Hat/CentOS
   /etc/pki/ca-trust/source/anchors/

   # Debian/Ubuntu
   /usr/local/share/ca-certificates/

   # macOS
   /etc/ssl/certs/
   ```

2. **Configure DevAIFlow:**
   ```json
   {
     "http_client": {
       "ssl_verify": "/etc/pki/ca-trust/source/anchors/company-ca.crt"
     }
   }
   ```

3. **Verify it works:**
   ```bash
   daf upgrade
   ```

## Environment Variables

All environment variables:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `DAF_SSL_VERIFY` | `true`, `false`, or path | `true` | SSL verification setting |
| `DAF_REQUEST_TIMEOUT` | Integer (seconds) | `10` | HTTP request timeout |

**Priority order:** Environment variable → Configuration file → Default

## Troubleshooting

### Error: "SSL: CERTIFICATE_VERIFY_FAILED"

**Cause:** Internal CA certificate not trusted by system.

When you encounter SSL certificate verification errors, DevAIFlow now provides **helpful error messages** with actionable solutions:

```
SSL certificate verification failed for https://gitlab.internal.example.com/.../ENTERPRISE.md
Error: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
       self-signed certificate in certificate chain

Solutions:
  1. Use custom CA bundle (RECOMMENDED for production):
     export DAF_SSL_VERIFY=/path/to/ca-bundle.crt
     daf upgrade

  2. Disable SSL verification (INSECURE - testing only):
     export DAF_SSL_VERIFY=false
     daf upgrade

  3. Configure permanently in organization.json:
     {
       "http_client": {
         "ssl_verify": "/path/to/ca-bundle.crt"
       }
     }

See docs/ssl-configuration.md for more information.
```

**Quick Solutions:**

1. **Use custom CA bundle (RECOMMENDED):**
   ```bash
   export DAF_SSL_VERIFY=/path/to/company-ca.crt
   daf upgrade
   ```

2. **Install CA certificate system-wide:**
   ```bash
   # Red Hat/CentOS
   sudo cp company-ca.crt /etc/pki/ca-trust/source/anchors/
   sudo update-ca-trust

   # Debian/Ubuntu
   sudo cp company-ca.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates
   ```

3. **Temporary workaround (INSECURE):**
   ```bash
   export DAF_SSL_VERIFY=false
   daf upgrade
   ```

### Warnings from urllib3

If you see:
```
InsecureRequestWarning: Unverified HTTPS request is being made to host 'example.com'
```

This is **expected** when `ssl_verify=false` and serves as a reminder that SSL verification is disabled.

To suppress (not recommended):
```bash
export PYTHONWARNINGS="ignore:Unverified HTTPS request"
```

## Examples

### Example 1: Internal GitLab with Self-Signed Certificate

```json
{
  "hierarchical_config_source": "https://gitlab.internal.company.com/devops/devaiflow-config/configs",
  "http_client": {
    "ssl_verify": "/etc/ssl/certs/internal-gitlab-ca.crt",
    "timeout": 30
  }
}
```

### Example 2: Corporate Proxy with SSL Inspection

```json
{
  "http_client": {
    "ssl_verify": "/etc/pki/ca-trust/source/anchors/corporate-proxy-ca.crt",
    "timeout": 60
  }
}
```

### Example 3: Development Environment (Local Testing Only)

```bash
# One-time use only - DO NOT commit this to version control
export DAF_SSL_VERIFY=false
daf upgrade
```

## Testing

Verify SSL configuration is working:

```bash
# Test with environment variable
export DAF_SSL_VERIFY=/path/to/ca-bundle.crt
daf upgrade

# Check what's configured
daf config show --json | jq '.http_client'
```

## Related Issues

- [#117](https://github.com/itdove/devaiflow/issues/117) - SSL certificate verification fails with internal GitLab

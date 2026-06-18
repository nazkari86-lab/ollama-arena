# ADR 006: CSP Security Improvements with Nonce-Based Policies

## Status
Accepted

## Context
The original Content Security Policy (CSP) implementation in ollama-arena's web interface used 'unsafe-inline' in both script-src and style-src directives. While this allowed the application to function with external CDN scripts, it represented a security vulnerability:
- 'unsafe-inline' allows any inline script to execute, bypassing CSP protections
- Increases XSS attack surface
- Defeats the purpose of CSP as a defense-in-depth measure
- Security scanners flag this as a high-severity issue

The application uses several external CDN libraries (Plotly, Three.js, etc.) that require script execution, making a strict CSP challenging without a more sophisticated approach.

## Decision
Implemented nonce-based CSP policies to eliminate 'unsafe-inline' while maintaining functionality:

### 1. CSP Nonce Management
- **CSPNonceManager**: Cryptographically secure nonce generation
- **CSPPolicyBuilder**: CSP policy construction with nonce support
- **Validation**: Nonce format validation to ensure security

### 2. Template Integration
- **CSPJinjaEnvironment**: Custom Jinja environment for nonce injection
- **Context Passing**: Automatic nonce context passing to templates
- **Middleware Integration**: SecurityHeadersMiddleware generates and injects nonces

### 3. Policy Structure
- Replaced 'unsafe-inline' with 'nonce-{value}' in script-src and style-src
- Maintained allow-lists for trusted CDNs
- Preserved strict policies for other directives (object-src 'none', frame-ancestors 'none')

### Changes Made

**File:** `ollama_arena/security/__init__.py`
- Package initialization for security utilities
- Exports CSPNonceManager and CSPPolicyBuilder

**File:** `ollama_arena/security/csp.py`
- `CSPNonceManager` class with generate_nonce() and validate_nonce_format()
- `CSPPolicyBuilder` class for policy construction
- Nonce generation using secrets.token_urlsafe (cryptographically secure)
- CSP policy building with configurable directives

**File:** `ollama_arena/web.py`
- Updated SecurityHeadersMiddleware to use CSPPolicyBuilder
- Replaced 'unsafe-inline' with nonce-based policy
- Added CSPJinjaEnvironment for template rendering
- Updated template rendering to pass nonce context
- Request state integration for nonce context storage

**Template:** `templates/base.html`
- No inline scripts (all external), so no nonce attributes needed
- Nonces in CSP header allow future inline scripts if needed

## Security Impact

### Before
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.plot.ly ...; style-src 'self' 'unsafe-inline' ...
```

### After
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-abc123...' https://cdn.plot.ly ...; style-src 'self' 'nonce-xyz789...' ...
```

### Security Improvements
- **XSS Protection**: Inline scripts without nonces are blocked
- **Attack Surface Reduction**: 'unsafe-inline' completely removed
- **Compliance**: Meets modern CSP best practices
- **Scanner Compliance**: Security scanners will no longer flag 'unsafe-inline'

## Consequences

### Positive
- **Enhanced Security**: Eliminates 'unsafe-inline' vulnerability
- **Standards Compliance**: Follows OWASP and security best practices
- **Backward Compatible**: No changes to template rendering needed (no inline scripts)
- **Flexible**: Nonce-based approach allows future inline scripts if needed
- **Automatic**: Nonce generation is transparent to application logic

### Negative
- **Middleware Dependency**: Requires custom middleware for nonce generation
- **State Management**: Nonce context must be passed through request state
- **Template Updates**: Future inline scripts require nonce attributes
- **Slight Complexity**: Additional abstraction layer for CSP management

## Technical Details

### Nonce Generation
- Uses `secrets.token_urlsafe(16)` for 128-bit entropy
- Base64url encoding results in ~22 character nonces
- Validation checks for alphanumeric + hyphen/underscore characters
- Length validation (16-64 characters)

### CSP Policy Structure
```python
policy = (
    f"default-src 'self'; "
    f"script-src 'self' 'nonce-{script_nonce}' {cdn_scripts}; "
    f"style-src 'self' 'nonce-{style_nonce}' {cdn_styles}; "
    f"font-src 'self' {cdn_fonts} data:; "
    f"img-src 'self' data: blob: https:; "
    f"connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "form-action 'self';"
)
```

### Template Integration
- Nonces generated per-request in middleware
- Stored in `request.state.csp_nonce_context`
- Available in templates as `{{ csp_nonces.script_nonce }}`
- CSPJinjaEnvironment handles automatic injection

## Browser Compatibility
- Nonce-based CSP is supported in all modern browsers:
  - Chrome 40+ (2015)
  - Firefox 31+ (2014)
  - Safari 10+ (2016)
  - Edge (all versions)
- Fallback for older browsers not implemented (security-first approach)

## Performance Impact
- Minimal overhead: ~0.1ms for nonce generation
- No additional network requests
- Middleware execution adds negligible latency
- Template rendering unchanged (no inline scripts)

## Usage Example

```python
from ollama_arena.security import CSPNonceManager, CSPPolicyBuilder

# Generate nonces
manager = CSPNonceManager()
script_nonce = manager.generate_nonce()
style_nonce = manager.generate_nonce()

# Build policy
builder = CSPPolicyBuilder(script_nonce, style_nonce)
policy = builder.build_policy(
    allow_scripts=["https://cdn.plot.ly"],
    allow_styles=["https://cdnjs.cloudflare.com"],
)

# Use in response
response.headers["Content-Security-Policy"] = policy
```

## Future Enhancements
- Add hash-based CSP for static inline scripts (if needed)
- Implement report-uri for CSP violation monitoring
- Add strict-dynamic for dynamic script loading
- Consider 'require-trusted-types-for' for additional DOM security

## Alternatives Considered

1. **Hash-based CSP**: Rejected because no static inline scripts exist
2. **Keep 'unsafe-inline'**: Rejected due to security vulnerability
3. **Separate CSP for development/production**: Rejected for consistency
4. **External CSP middleware**: Rejected to maintain control and reduce dependencies
5. **Disallow all CDNs**: Rejected due to functionality requirements

## References
- CSP implementation in `ollama_arena/security/csp.py`
- Web middleware updates in `ollama_arena/web.py`
- OWASP CSP Guidelines: https://owasp.org/www-project-web-security-testing-guide/
- MDN CSP Documentation: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- CSP Level 3 Specification: https://www.w3.org/TR/CSP3/

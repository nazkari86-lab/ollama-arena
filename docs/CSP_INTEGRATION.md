# CSP Integration Guide

## Overview
Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks, including Cross Site Scripting (XSS) and data injection attacks.

## Implementation

### 1. Add CSP Middleware to FastAPI App

```python
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from ollama_arena.security import CSPMiddleware

app = FastAPI()

# Add CSP middleware
app.add_middleware(CSPMiddleware)

# Or use strict CSP (no unsafe-inline)
# app.add_middleware(StrictCSPMiddleware)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    # Get nonce from request state
    csp_nonce = getattr(request.state, 'csp_nonce', '')
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "csp_nonce": csp_nonce}
    )
```

### 2. Update HTML Templates

Add `nonce` attribute to all inline scripts and update CSP meta tag:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" 
          content="default-src 'self'; 
                   script-src 'self' 'nonce-{{ csp_nonce }}' https://cdn.plot.ly; 
                   style-src 'self' 'nonce-{{ csp_nonce }}' 'unsafe-inline' https://fonts.googleapis.com;">
    
    <!-- External scripts with nonce -->
    <script nonce="{{ csp_nonce }}" src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    
    <!-- Inline scripts must use nonce -->
    <script nonce="{{ csp_nonce }}">
        // Your inline JavaScript code
    </script>
</head>
<body>
    <!-- Content -->
</body>
</html>
```

### 3. Migration Steps

#### Step 1: Add Nonce to All Inline Scripts
Replace all inline `<script>` tags with nonce attribute:

**Before:**
```html
<script>
    console.log("Hello");
</script>
```

**After:**
```html
<script nonce="{{ csp_nonce }}">
    console.log("Hello");
</script>
```

#### Step 2: Update External Scripts
Add nonce to external script tags:

**Before:**
```html
<script src="/static/app.js"></script>
```

**After:**
```html
<script nonce="{{ csp_nonce }}" src="/static/app.js"></script>
```

#### Step 3: Handle Dynamic Content
For dynamically generated scripts, add nonce programmatically:

```python
# In your route handler
def add_script_nonce(request: Request, html_content: str) -> str:
    """Add CSP nonce to all script tags in HTML."""
    csp_nonce = getattr(request.state, 'csp_nonce', '')
    
    # Replace script tags with nonce
    import re
    pattern = r'(<script)([^>]*)(>)'
    replacement = rf'\1 nonce="{csp_nonce}"\2\3'
    
    return re.sub(pattern, replacement, html_content)
```

### 4. CSP Policy Options

#### Standard CSP (allows unsafe-inline for styles)
```python
from ollama_arena.security import CSPMiddleware
app.add_middleware(CSPMiddleware)
```

This allows:
- `script-src 'self' 'nonce-{nonce}'` - Scripts from same origin with valid nonce
- `style-src 'self' 'nonce-{nonce}' 'unsafe-inline'` - Styles with nonce or inline
- All other restrictions apply

#### Strict CSP (no unsafe-inline)
```python
from ollama_arena.security import StrictCSPMiddleware  
app.add_middleware(StrictCSPMiddleware)
```

This is more restrictive:
- No `unsafe-inline` for styles
- All inline content must use nonce
- Better security but requires more changes

### 5. Testing CSP Implementation

#### Test CSP Compliance
```bash
# Use browser console to check for CSP violations
# Open DevTools -> Console -> Look for CSP warnings
```

#### Test with CSP Evaluator
```bash
# Online CSP evaluator
# https://csp-evaluator.withgoogle.com/
```

#### Test Security Headers
```bash
# Check CSP header
curl -I http://localhost:8000

# Look for:
# Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-...'
```

### 6. Troubleshooting

#### Issue: Scripts not loading
**Cause:** Missing nonce attribute on script tags
**Solution:** Add `nonce="{{ csp_nonce }}"` to all script tags

#### Issue: Styles not applying
**Cause:** Inline styles without nonce (in strict mode)
**Solution:** Move styles to external CSS files or use nonce

#### Issue: External resources blocked
**Cause:** Domain not in CSP whitelist
**Solution:** Add domain to appropriate CSP directive

#### Issue: Dynamic content blocked
**Cause:** Dynamic scripts without nonce
**Solution:** Use the `add_script_nonce()` helper function

### 7. Security Benefits

1. **XSS Prevention**: Prevents execution of unauthorized scripts
2. **Data Injection Protection**: Blocks unauthorized data loading
3. **Clickjacking Protection**: Prevents site from being framed
4. **Mixed Content Protection**: Blocks HTTP content on HTTPS pages

### 8. Performance Considerations

- **Minimal overhead**: CSP adds ~1-2ms to response time
- **Browser caching**: CSP policies are cached by browsers
- **No impact on legitimate content**: Properly configured CSP doesn't block authorized resources

### 9. Gradual Rollout Strategy

1. **Report-Only Mode**: Test CSP without blocking
   ```python
   # Use report-uri to get reports without blocking
   csp_policy += f"; report-uri {report_endpoint}"
   ```

2. **Monitor Reports**: Check CSP violation reports
   ```python
   @app.post("/csp-report")
   async def csp_report(request: Request):
       report = await request.json()
       # Log or analyze CSP violations
   ```

3. **Enforce Gradually**: Start with permissive policy, tighten over time

### 10. Browser Compatibility

CSP Level 2 (with nonce) is supported in:
- Chrome 25+
- Firefox 23+
- Safari 7+
- Edge 12+
- Opera 15+

For older browsers, consider fallback:
```python
# Add X-Content-Security-Policy for older browsers
response.headers["X-Content-Security-Policy"] = csp_policy
```
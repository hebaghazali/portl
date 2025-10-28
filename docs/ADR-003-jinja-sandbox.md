# ADR-003: Jinja2 Template Sandbox

## Status
**Accepted** (PR#2)

## Context

Portl job configurations use Jinja2 templates for dynamic value interpolation:

```yaml
steps:
  - id: create_order
    type: db.insert
    config:
      table: orders
      mapping:
        order_id: "{{ user_input | md5 }}"
        created_at: "{{ now() }}"
```

User-provided templates could potentially execute arbitrary code via Jinja2's introspection capabilities:

```jinja2
{{ ''.__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['sys'].exit() }}
```

This is a **critical security vulnerability** for multi-tenant systems or when running untrusted job definitions.

## Decision

### Use SandboxedEnvironment with Attribute Allowlist

Portl templates execute in a **sandboxed Jinja2 environment** with:

1. **`SandboxedEnvironment`** instead of `Environment`
   - Prevents access to object internals
   - Blocks method calls on unsafe objects

2. **Strict attribute access control** via `is_safe_attribute()`
   - Block all private attributes (starting with `_`)
   - Block class introspection (`__class__`, `__bases__`, `__subclasses__`, `__mro__`)
   - Block dangerous builtins (`eval`, `exec`, `compile`, `open`, `__import__`)

3. **Allowlist approach for filters and globals**
   - Only explicitly registered functions are available
   - Clear existing environment and register safe subset

4. **StrictUndefined** enforcement
   - Fail loud on missing template variables
   - Prevents typos and undefined behavior

### Allowlisted Filters

```python
SAFE_FILTERS = {
    # Hash and encoding
    'md5',
    
    # JSON
    'tojson', 'fromjson',
    
    # Type conversion
    'int', 'float', 'str', 'bool',
    
    # String manipulation
    'upper', 'lower', 'trim',
    
    # Null handling
    'coalesce', 'default',
    
    # Data extraction
    'json_path',
}
```

### Allowlisted Globals

```python
SAFE_GLOBALS = {
    'now',     # Current timestamp
    'range',   # Python range() for loops
}
```

### Security Tests

18 tests verify sandbox behavior:
- ✅ Blocks `__class__`, `__bases__`, `__subclasses__`
- ✅ Blocks `__builtins__`, `__globals__`, `__import__`
- ✅ Blocks `eval`, `exec`, `compile`, `open`
- ✅ Allows safe operations (filters, globals, variable access)

## Consequences

### Positive
- ✅ **Prevents code injection**: Users cannot execute arbitrary Python
- ✅ **Safe for multi-tenant use**: Each job runs in isolated sandbox
- ✅ **Clear error messages**: StrictUndefined helps debug template errors
- ✅ **Fail-safe default**: Attribute allowlist means new Python features don't create vulnerabilities

### Negative
- ❌ **Limited expressiveness**: Cannot use arbitrary Python expressions
- ❌ **Maintenance burden**: Must explicitly add new helpers to allowlist
- ❌ **Performance overhead**: Sandbox attribute checks add slight latency

### Trade-offs

**Why not just disable template execution for untrusted jobs?**
- Templates are core to Portl's value proposition (dynamic workflows)
- Disabling them would require duplicating job definitions

**Why allowlist instead of blocklist?**
- Blocklists are incomplete (new Python features, subtle bypasses)
- Allowlists are fail-safe (unknown = blocked)

**Why not use a separate template language?**
- Jinja2 is well-tested, widely understood, and has good tooling
- Custom languages are hard to get right and lack ecosystem

## Implementation

### Before (Vulnerable)
```python
from jinja2 import Environment, StrictUndefined

env = Environment(undefined=StrictUndefined)
env.filters.update(...)  # All Jinja2 filters available
```

### After (Secure)
```python
from jinja2.sandbox import SandboxedEnvironment

class TemplateEngine:
    def __init__(self):
        self.env = SandboxedEnvironment(undefined=StrictUndefined)
        self.env.is_safe_attribute = self._is_safe_attribute
        self._register_safe_helpers()  # Allowlist only
    
    def _is_safe_attribute(self, obj, attr, value):
        if attr.startswith('_'):
            return False  # Block private
        if attr in BLOCKED_ATTRS:
            return False  # Block dangerous
        return True
```

## Validation

Users attempting template escapes will see:
```
jinja2.exceptions.SecurityError: access to attribute '__class__' of 'str' object is unsafe.
```

Safe operations continue to work:
```jinja2
{{ user.email | lower }}  ✅
{{ order.amount | int }}  ✅
{{ now() }}               ✅
```

## Future Evolution

- **Configurable sandbox levels**: Strict (current) vs relaxed (for trusted jobs)
- **Additional safe helpers**: Date formatting, regex, base64 encoding
- **Template compilation caching**: Pre-compile templates for performance
- **Audit logging**: Log which templates are rendered and by whom

## References

- [Jinja2 Sandbox Documentation](https://jinja.palletsprojects.com/en/3.1.x/sandbox/)
- [OWASP Template Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/18-Testing_for_Server-side_Template_Injection)
- [Shopify Liquid Security](https://shopify.github.io/liquid/basics/security/)

---

**Author**: Backend Team  
**Date**: 2025-10-28  
**Supersedes**: None


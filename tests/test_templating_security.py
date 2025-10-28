"""
Security tests for Jinja2 template sandboxing.

Tests that malicious templates cannot escape the sandbox and that
safe operations continue to work correctly.
"""

import pytest
from jinja2.sandbox import SecurityError
from jinja2 import UndefinedError

from portl.execution.templating import get_template_engine


class TestTemplatingSecurity:
    """Test suite for template sandboxing security."""
    
    def test_blocks_private_attribute_access(self):
        """Verify that templates cannot access private attributes."""
        engine = get_template_engine()
        
        # Try to access __class__
        with pytest.raises((SecurityError, UndefinedError)):
            engine.render_string("{{ ''.__class__ }}", {})
    
    def test_blocks_class_introspection(self):
        """Verify that templates cannot introspect class hierarchy."""
        engine = get_template_engine()
        
        malicious_templates = [
            "{{ ''.__class__ }}",
            "{{ ''.__class__.__bases__ }}",
            "{{ ''.__class__.__mro__ }}",
            "{{ ().__class__.__bases__[0].__subclasses__() }}",
        ]
        
        for template in malicious_templates:
            with pytest.raises((SecurityError, UndefinedError)):
                engine.render_string(template, {})
    
    def test_blocks_builtins_access(self):
        """Verify that templates cannot access __builtins__."""
        engine = get_template_engine()
        
        malicious_templates = [
            "{{ [].__class__.__base__.__subclasses__()[104].__init__.__globals__['__builtins__'] }}",
            "{{ ().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__ }}",
        ]
        
        for template in malicious_templates:
            with pytest.raises((SecurityError, UndefinedError)):
                engine.render_string(template, {})
    
    def test_blocks_file_system_access(self):
        """Verify that templates cannot access file system."""
        engine = get_template_engine()
        
        # These should all fail due to lack of 'open' in globals
        malicious_templates = [
            "{{ open('/etc/passwd').read() }}",
            "{{ __import__('os').system('ls') }}",
        ]
        
        for template in malicious_templates:
            with pytest.raises((UndefinedError, SecurityError)):
                engine.render_string(template, {})
    
    def test_blocks_import_statements(self):
        """Verify that templates cannot import modules."""
        engine = get_template_engine()
        
        malicious_templates = [
            "{{ __import__('os') }}",
            "{{ __import__('subprocess').call('ls') }}",
        ]
        
        for template in malicious_templates:
            with pytest.raises(UndefinedError):
                engine.render_string(template, {})
    
    def test_blocks_eval_exec(self):
        """Verify that templates cannot use eval/exec."""
        engine = get_template_engine()
        
        malicious_templates = [
            "{{ eval('1+1') }}",
            "{{ exec('import os') }}",
            "{{ compile('1+1', '', 'eval') }}",
        ]
        
        for template in malicious_templates:
            with pytest.raises(UndefinedError):
                engine.render_string(template, {})
    
    # Positive tests - verify safe operations still work
    
    def test_safe_string_operations_work(self):
        """Verify that safe string operations still work."""
        engine = get_template_engine()
        
        assert engine.render_string("{{ 'hello' | upper }}", {}) == "HELLO"
        assert engine.render_string("{{ 'HELLO' | lower }}", {}) == "hello"
        assert engine.render_string("{{  ' test ' | trim }}", {}) == "test"
    
    def test_safe_type_conversions_work(self):
        """Verify that safe type conversions still work."""
        engine = get_template_engine()
        
        assert engine.render_string("{{ '123' | int }}", {}) == "123"
        assert engine.render_string("{{ '45.67' | float }}", {}) == "45.67"
        assert engine.render_string("{{ 42 | str }}", {}) == "42"
    
    def test_safe_json_operations_work(self):
        """Verify that JSON operations still work."""
        engine = get_template_engine()
        
        # tojson
        result = engine.render_string("{{ data | tojson }}", {'data': {'key': 'value'}})
        assert '"key"' in result
        assert '"value"' in result
        
        # fromjson
        result = engine.render_string('{{ json_str | fromjson }}', {'json_str': '{"key": "value"}'})
        assert result  # Should parse without error
    
    def test_safe_md5_helper_works(self):
        """Verify that md5 helper still works."""
        engine = get_template_engine()
        
        result = engine.render_string("{{ 'test' | md5 }}", {})
        assert len(result) == 32  # MD5 hash is 32 hex chars
        assert result == '098f6bcd4621d373cade4e832627b4f6'  # Known MD5 of 'test'
    
    def test_safe_now_helper_works(self):
        """Verify that now() helper still works."""
        engine = get_template_engine()
        
        result = engine.render_string("{{ now() }}", {})
        assert 'T' in result  # ISO format timestamp
        assert len(result) > 10  # Reasonable timestamp length
    
    def test_safe_coalesce_works(self):
        """Verify that coalesce filter still works."""
        engine = get_template_engine()
        
        result = engine.render_string(
            "{{ value | coalesce(None, None, 'default') }}", 
            {'value': None}
        )
        assert result == "default"
    
    def test_safe_json_path_works(self):
        """Verify that json_path filter still works."""
        engine = get_template_engine()
        
        data = {
            'user': {
                'address': {
                    'city': 'New York'
                }
            }
        }
        
        result = engine.render_string(
            "{{ data | json_path('user.address.city') }}", 
            {'data': data}
        )
        assert result == "New York"
    
    def test_safe_range_works(self):
        """Verify that range() builtin still works."""
        engine = get_template_engine()
        
        result = engine.render_string(
            "{% for i in range(3) %}{{ i }}{% endfor %}", 
            {}
        )
        assert result == "012"
    
    def test_context_variable_access_works(self):
        """Verify that normal variable access still works."""
        engine = get_template_engine()
        
        context = {
            'name': 'Alice',
            'age': 30,
            'data': {'key': 'value'}
        }
        
        assert engine.render_string("{{ name }}", context) == "Alice"
        assert engine.render_string("{{ age }}", context) == "30"
        assert engine.render_string("{{ data.key }}", context) == "value"
    
    def test_strict_undefined_still_enforced(self):
        """Verify that StrictUndefined is still enforced."""
        engine = get_template_engine()
        
        # Accessing undefined variable should raise error
        with pytest.raises(UndefinedError):
            engine.render_string("{{ undefined_var }}", {})
    
    def test_nested_attribute_access_safe(self):
        """Verify that nested attribute access works for safe objects."""
        engine = get_template_engine()
        
        context = {
            'user': {
                'profile': {
                    'name': 'Bob',
                    'email': 'bob@example.com'
                }
            }
        }
        
        result = engine.render_string("{{ user.profile.name }}", context)
        assert result == "Bob"
    
    def test_cannot_access_dict_private_methods(self):
        """Verify that private methods on dicts are blocked."""
        engine = get_template_engine()
        
        context = {'data': {'key': 'value'}}
        
        # Try to access __class__ on dict
        with pytest.raises((SecurityError, UndefinedError)):
            engine.render_string("{{ data.__class__ }}", context)


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])


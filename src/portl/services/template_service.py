from pathlib import Path


class TemplateService:
    def __init__(self):
        self._template_source = Path(__file__).parent.parent / "template.yaml"
    
    def get_template_content(self) -> str:
        try:
            with open(self._template_source, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Template file not found at {self._template_source}")
    
    def create_template_file(self, output_path: Path, overwrite: bool = False) -> bool:
        """
        Create a template file at the specified path.
        
        Args:
            output_path: Path where to create the template
            overwrite: Whether to overwrite existing file
            
        Returns:
            bool: True if template was created, False if cancelled
            
        Raises:
            FileExistsError: If file exists and overwrite=False
            FileNotFoundError: If source template is not found
        """
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Template file already exists: {output_path}")
        
        template_content = self.get_template_content()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        return True
    
    def get_default_template_name(self) -> str:
        """Get the default template filename."""
        return "portl_template.yaml"

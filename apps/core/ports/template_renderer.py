"""
Port (Interface) for template rendering.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class TemplateRenderer(ABC):
    """
    Port: Abstract interface for template rendering.
    Allows different template engines to be plugged in.
    """

    @abstractmethod
    def render(self, template_body: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_body: The template string with placeholders
            context: Dictionary of variable values

        Returns:
            The rendered string with placeholders replaced
        """
        pass

    @abstractmethod
    def get_variables(self, template_body: str) -> List[str]:
        """
        Extract variable names from a template.

        Args:
            template_body: The template string to parse

        Returns:
            List of variable names found in the template
        """
        pass

    def validate_template(
        self,
        template_body: str,
        available_vars: List[str]
    ) -> List[str]:
        """
        Validate that all template variables are in the available list.

        Args:
            template_body: The template string to validate
            available_vars: List of available variable names

        Returns:
            List of missing variables (empty if all valid)
        """
        template_vars = self.get_variables(template_body)
        available_lower = [v.lower() for v in available_vars]
        missing = [v for v in template_vars if v.lower() not in available_lower]
        return missing

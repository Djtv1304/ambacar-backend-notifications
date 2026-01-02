"""
Template rendering service.
"""
import re
from typing import Any, Dict, List

from apps.core.ports import TemplateRenderer


class TemplateService(TemplateRenderer):
    """
    Template renderer using {{variable}} syntax (like Mustache/Handlebars).

    Supports case-insensitive variable matching:
    - {{Nombre}}, {{nombre}}, {{NOMBRE}} all match 'nombre' in context

    Example:
        service = TemplateService()
        result = service.render(
            "Hola {{Nombre}}, tu vehículo {{Placa}} está listo.",
            {"nombre": "Carlos", "placa": "ABC123"}
        )
        # Result: "Hola Carlos, tu vehículo ABC123 está listo."
    """

    VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def render(self, template_body: str, context: Dict[str, Any]) -> str:
        """
        Replace {{variable}} placeholders with context values.
        Case-insensitive matching for variable names.

        Args:
            template_body: Template string with {{variable}} placeholders
            context: Dictionary of variable values

        Returns:
            Rendered string with placeholders replaced
        """
        # Create lowercase key mapping for case-insensitive lookup
        context_lower = {k.lower(): v for k, v in context.items()}

        def replace_variable(match):
            var_name = match.group(1).lower()
            if var_name in context_lower:
                value = context_lower[var_name]
                return str(value) if value is not None else ""
            # Keep original if not found
            return match.group(0)

        return self.VARIABLE_PATTERN.sub(replace_variable, template_body)

    def get_variables(self, template_body: str) -> List[str]:
        """
        Extract all variable names from the template.

        Args:
            template_body: Template string to parse

        Returns:
            List of unique variable names found
        """
        matches = self.VARIABLE_PATTERN.findall(template_body)
        return list(set(matches))

    def preview_template(self, template_body: str, example_values: Dict[str, str] = None) -> str:
        """
        Preview a template with example values.
        Uses default examples if not provided.

        Args:
            template_body: Template to preview
            example_values: Optional custom example values

        Returns:
            Rendered preview string
        """
        from apps.core.constants import TEMPLATE_VARIABLES

        # Build default examples from constants
        default_examples = {
            var["id"]: var["example"]
            for var in TEMPLATE_VARIABLES
        }

        # Merge with provided examples
        context = {**default_examples, **(example_values or {})}

        return self.render(template_body, context)

    def get_template_stats(self, template_body: str) -> Dict[str, int]:
        """
        Get statistics about a template.

        Returns:
            Dict with characters, words, and variables count
        """
        characters = len(template_body)
        words = len(template_body.split())
        variables = len(self.get_variables(template_body))

        return {
            "characters": characters,
            "words": words,
            "variables": variables,
        }


# Singleton instance for convenience
template_service = TemplateService()

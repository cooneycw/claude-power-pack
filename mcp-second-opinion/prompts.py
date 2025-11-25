"""Prompt templates for code review and analysis."""

import re
from typing import List, Optional


def scan_for_secrets(code: str) -> List[str]:
    """
    Scan code for potential secrets before sending to API.

    Returns list of potential secret patterns found.
    """
    secret_patterns = [
        (r'[A-Za-z0-9]{20,}', 'Long alphanumeric string (potential API key)'),
        (r'sk-[A-Za-z0-9]{20,}', 'OpenAI API key pattern'),
        (r'AIza[A-Za-z0-9_-]{35}', 'Google AI/Firebase API key'),
        (r'github_pat_[A-Za-z0-9]{22,}', 'GitHub personal access token'),
        (r'ghp_[A-Za-z0-9]{36,}', 'GitHub token'),
        (r'glpat-[A-Za-z0-9_-]{20,}', 'GitLab personal access token'),
        (r'-----BEGIN [A-Z ]+PRIVATE KEY-----', 'Private key'),
        (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
        (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
    ]

    found_secrets = []
    for pattern, description in secret_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            found_secrets.append(description)

    return found_secrets


def build_code_review_prompt(
    code: str,
    language: str,
    context: Optional[str] = None,
    error_messages: Optional[List[str]] = None,
    issue_description: Optional[str] = None,
    verbosity: str = "detailed",
) -> str:
    """
    Build a structured prompt for code review using XML delimiters.

    Uses XML tags to prevent prompt injection and separate instructions from data.

    Args:
        code: The code to review
        language: Programming language of the code
        context: Additional context about the code
        error_messages: List of error messages encountered
        issue_description: Description of the issue or challenge
        verbosity: "brief" or "detailed" (controls output length)

    Returns:
        Formatted prompt string for the LLM
    """
    # Build input data section with XML tags
    input_data_parts = [f"<language>{language}</language>"]

    if context:
        input_data_parts.append(f"<context>\n{context}\n</context>")

    if issue_description:
        input_data_parts.append(f"<issue_description>\n{issue_description}\n</issue_description>")

    if error_messages:
        errors_str = "\n".join(f"- {err}" for err in error_messages)
        input_data_parts.append(f"<error_messages>\n{errors_str}\n</error_messages>")

    # Wrap code in XML tags to prevent injection
    input_data_parts.append(f"<source_code>\n{code}\n</source_code>")

    input_data_section = "\n".join(input_data_parts)

    # Build instructions based on verbosity
    if verbosity == "brief":
        analysis_structure = """
Provide your response with:

1. **Root Cause Analysis** (1-2 sentences)
2. **Severity & Quick Fix** (Combine assessment with immediate code fix)
3. **Confidence Score** (0-100%)

Keep it concise and actionable.
"""
    else:  # detailed
        analysis_structure = """
Provide a comprehensive second opinion with:

1. **Root Cause Analysis** - Identify core issue(s) specifically
2. **Severity Assessment** (Critical | High | Medium | Low)
3. **Specific Recommendations** - Actionable fixes with code examples
4. **Alternative Approaches** - 2-3 different solutions with trade-offs
5. **Best Practices** - Relevant coding standards and patterns
6. **Security Considerations** - Flag security implications
7. **Confidence Level** (0-100%)
"""

    # Construct final prompt
    prompt = f"""You are a senior software engineer providing a second opinion on challenging coding issues.

# Input Data
{input_data_section}

# Instructions

Analyze the content within <source_code> tags.
Use the context provided in <context> or <issue_description> to guide your analysis.

{analysis_structure}

IMPORTANT:
- Return your response in Markdown format
- Do not repeat the code unless suggesting a fix
- Be specific and actionable
- Focus on what matters most
"""

    return prompt.strip()

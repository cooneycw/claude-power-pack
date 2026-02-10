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
    code_files: Optional[list] = None,
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
        verbosity: "brief", "detailed", or "in_depth" (controls output depth)
        code_files: Optional list of additional files, each a dict with
                    "filename" and "content" keys

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

    # Add additional code files if provided
    if code_files:
        for i, file_info in enumerate(code_files):
            filename = file_info.get("filename", f"file_{i + 1}")
            content = file_info.get("content", "")
            if content:
                input_data_parts.append(
                    f'<additional_file name="{filename}">\n{content}\n</additional_file>'
                )

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
    elif verbosity == "in_depth":
        analysis_structure = """
Provide an exhaustive, in-depth second opinion. You have extensive output space available,
so be thorough and leave nothing unexamined. Cover ALL of the following:

1. **Root Cause Analysis** - Deep dive into every core issue, including subtle ones.
   Trace the logical flow and identify all failure modes.
2. **Severity Assessment** (Critical | High | Medium | Low) - Per-issue severity with justification
3. **Detailed Recommendations** - Comprehensive, actionable fixes with full code examples.
   Show before/after comparisons where helpful.
4. **Alternative Approaches** - 3-5 different solutions with detailed trade-off analysis
   covering performance, maintainability, testability, and complexity
5. **Architecture & Design Patterns** - Evaluate the overall design. Suggest applicable
   design patterns, SOLID principles, and structural improvements.
6. **Best Practices & Standards** - Relevant coding standards, language idioms,
   community conventions, and linting rules
7. **Security Audit** - Thorough security analysis: injection risks, auth issues,
   data exposure, OWASP considerations, supply chain concerns
8. **Performance Analysis** - Time/space complexity, bottlenecks, caching opportunities,
   database query optimization, memory usage
9. **Testing Strategy** - Recommended unit tests, integration tests, edge cases to cover,
   mocking strategies, and test data considerations
10. **Error Handling & Resilience** - Exception handling gaps, retry logic, graceful
    degradation, logging, and observability improvements
11. **Documentation & Readability** - Code clarity, naming conventions, comments,
    docstring quality, and API documentation
12. **Confidence Level** (0-100%) with detailed justification

Be comprehensive. Provide code examples for every recommendation where applicable.
"""
    else:  # detailed (default)
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
    has_additional_files = bool(code_files)
    files_instruction = (
        "\nAlso analyze the content within <additional_file> tags as supporting context. "
        "Consider cross-file interactions, imports, and dependencies."
        if has_additional_files else ""
    )

    prompt = f"""You are a senior software engineer providing a second opinion on challenging coding issues.

# Input Data
{input_data_section}

# Instructions

Analyze the content within <source_code> tags.{files_instruction}
Use the context provided in <context> or <issue_description> to guide your analysis.

{analysis_structure}

IMPORTANT:
- Return your response in Markdown format
- Do not repeat the code unless suggesting a fix
- Be specific and actionable
- Focus on what matters most
"""

    return prompt.strip()

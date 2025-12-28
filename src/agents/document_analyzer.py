"""Document Analyzer agent for deep document analysis."""

from typing import Dict, Any, List

from src.agents.base import BaseAgent


class DocumentAnalyzerAgent(BaseAgent):
    """Agent for analyzing documents to extract insights and patterns."""

    name = "document_analyzer"
    description = "Analyzes documents to extract key themes, entities, and insights"

    def __init__(self, **kwargs):
        """Initialize the document analyzer agent."""
        super().__init__(temperature=0.3, max_tokens=2000, **kwargs)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for document analysis."""
        return """You are an expert document analyst. Your task is to provide comprehensive analysis of documents, extracting:

1. **Key Themes**: Identify the main topics and themes discussed in the document.

2. **Important Entities**: Extract and categorize entities such as:
   - People (names, roles, relationships)
   - Organizations (companies, institutions)
   - Locations (places, addresses)
   - Dates and times
   - Monetary values
   - Technical terms

3. **Main Arguments/Conclusions**: Summarize the key arguments or conclusions presented.

4. **Document Structure**: Describe how the document is organized.

5. **Relationships**: Identify connections between concepts, entities, or ideas.

6. **Sentiment/Tone**: Analyze the overall tone and any emotional aspects.

7. **Action Items/Recommendations**: Extract any recommended actions or next steps.

Provide your analysis in a structured, well-organized format with clear headings.
Be thorough but concise. Focus on actionable insights."""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Analyze the document(s).

        Args:
            input_data: Must contain 'query' with analysis request.
            context: Document content chunks to analyze.

        Returns:
            Dictionary with analysis results.
        """
        query = input_data.get("query", "Analyze this document")
        analysis_type = input_data.get("analysis_type", "comprehensive")

        if not context:
            return {
                "analysis": "No document content provided for analysis.",
                "error": "Missing context",
            }

        # Prepare the document content
        document_content = "\n\n---\n\n".join(
            f"Section {i+1}:\n{chunk}" for i, chunk in enumerate(context)
        )

        # Build the analysis prompt
        prompt = self._build_analysis_prompt(query, document_content, analysis_type)

        # Generate analysis
        analysis = await self.generate_response(prompt)

        return {
            "analysis": analysis,
            "analysis_type": analysis_type,
            "sections_analyzed": len(context),
            "query": query,
        }

    def _build_analysis_prompt(
        self,
        query: str,
        content: str,
        analysis_type: str,
    ) -> str:
        """Build the analysis prompt based on type.

        Args:
            query: The user's analysis request.
            content: Document content to analyze.
            analysis_type: Type of analysis to perform.

        Returns:
            The formatted prompt.
        """
        if analysis_type == "entities":
            return f"""Extract all entities from the following document:

{content}

Focus on identifying:
- People (with roles if mentioned)
- Organizations
- Locations
- Dates and times
- Key technical terms

User request: {query}"""

        elif analysis_type == "themes":
            return f"""Identify the main themes and topics in the following document:

{content}

For each theme:
1. Name the theme
2. Provide supporting evidence from the text
3. Explain its significance

User request: {query}"""

        elif analysis_type == "summary":
            return f"""Provide a detailed summary of the following document:

{content}

Include:
- Main purpose of the document
- Key points and arguments
- Conclusions or recommendations

User request: {query}"""

        else:  # comprehensive
            return f"""Perform a comprehensive analysis of the following document:

{content}

Provide:
1. Executive Summary
2. Key Themes and Topics
3. Important Entities (people, organizations, dates)
4. Main Arguments or Conclusions
5. Notable Patterns or Relationships
6. Recommendations or Action Items (if any)

User request: {query}"""

    async def extract_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract named entities from content.

        Args:
            content: Text content to analyze.

        Returns:
            Dictionary of entity types to lists of entities.
        """
        result = await self.execute(
            input_data={"query": "Extract all entities", "analysis_type": "entities"},
            context=[content],
        )
        return result

    async def identify_themes(self, content: str) -> Dict[str, Any]:
        """Identify main themes in content.

        Args:
            content: Text content to analyze.

        Returns:
            Dictionary with identified themes.
        """
        result = await self.execute(
            input_data={"query": "Identify main themes", "analysis_type": "themes"},
            context=[content],
        )
        return result
"""Summarizer agent for creating concise summaries."""

from typing import Dict, Any, List
from enum import Enum

from src.agents.base import BaseAgent


class SummaryLength(str, Enum):
    """Summary length options."""
    SHORT = "short"  # 1-2 sentences
    MEDIUM = "medium"  # 1 paragraph
    LONG = "long"  # Multiple paragraphs


class SummarizerAgent(BaseAgent):
    """Agent for creating concise summaries of documents and content."""

    name = "summarizer"
    description = "Creates clear, concise summaries of documents and content"

    def __init__(self, **kwargs):
        """Initialize the summarizer agent."""
        super().__init__(temperature=0.3, max_tokens=1500, **kwargs)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for summarization."""
        return """You are an expert summarizer. Your task is to create clear, accurate, and concise summaries.

Follow these principles:
1. **Accuracy**: Preserve the original meaning and key facts
2. **Clarity**: Use clear, simple language
3. **Completeness**: Include all essential information
4. **Conciseness**: Eliminate redundancy and unnecessary details
5. **Structure**: Organize information logically

Summary guidelines:
- Start with the most important information
- Use bullet points for multiple key points
- Maintain objective tone unless the original is opinion-based
- Preserve important numbers, dates, and names
- Indicate if information is unclear or ambiguous in the source"""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Create a summary of the content.

        Args:
            input_data: Contains 'query' and optional 'length' setting.
            context: Content chunks to summarize.

        Returns:
            Dictionary with the summary and metadata.
        """
        query = input_data.get("query", "Summarize this content")
        length = input_data.get("length", SummaryLength.MEDIUM.value)
        format_type = input_data.get("format", "paragraph")

        if not context:
            return {
                "summary": "No content provided for summarization.",
                "error": "Missing context",
            }

        # Combine context
        content = "\n\n".join(context)
        word_count = len(content.split())

        # Build the summarization prompt
        prompt = self._build_summary_prompt(query, content, length, format_type)

        # Generate summary
        summary = await self.generate_response(prompt)

        return {
            "summary": summary,
            "length": length,
            "format": format_type,
            "original_word_count": word_count,
            "summary_word_count": len(summary.split()),
            "compression_ratio": round(len(summary.split()) / word_count, 2) if word_count > 0 else 0,
        }

    def _build_summary_prompt(
        self,
        query: str,
        content: str,
        length: str,
        format_type: str,
    ) -> str:
        """Build the summarization prompt.

        Args:
            query: User's summarization request.
            content: Content to summarize.
            length: Desired summary length.
            format_type: Output format (paragraph, bullets, etc.).

        Returns:
            The formatted prompt.
        """
        length_instructions = {
            SummaryLength.SHORT.value: "Provide a very brief summary in 1-2 sentences.",
            SummaryLength.MEDIUM.value: "Provide a summary in one paragraph (3-5 sentences).",
            SummaryLength.LONG.value: "Provide a comprehensive summary with multiple paragraphs covering all key points.",
        }

        format_instructions = {
            "paragraph": "Write in paragraph form.",
            "bullets": "Use bullet points for key information.",
            "numbered": "Use a numbered list format.",
            "executive": "Format as an executive summary with sections.",
        }

        length_inst = length_instructions.get(length, length_instructions[SummaryLength.MEDIUM.value])
        format_inst = format_instructions.get(format_type, format_instructions["paragraph"])

        return f"""Please summarize the following content.

{length_inst}
{format_inst}

Content to summarize:
{content}

User request: {query}

Summary:"""

    async def summarize_for_length(
        self,
        content: str,
        length: SummaryLength,
    ) -> str:
        """Create a summary of specific length.

        Args:
            content: Content to summarize.
            length: Desired summary length.

        Returns:
            The generated summary.
        """
        result = await self.execute(
            input_data={"query": "Summarize this content", "length": length.value},
            context=[content],
        )
        return result.get("summary", "")

    async def create_bullet_summary(self, content: str) -> str:
        """Create a bullet-point summary.

        Args:
            content: Content to summarize.

        Returns:
            Bullet-point summary.
        """
        result = await self.execute(
            input_data={
                "query": "Create a bullet-point summary",
                "format": "bullets",
                "length": SummaryLength.MEDIUM.value,
            },
            context=[content],
        )
        return result.get("summary", "")

    async def create_executive_summary(self, content: str) -> str:
        """Create an executive summary.

        Args:
            content: Content to summarize.

        Returns:
            Executive summary.
        """
        result = await self.execute(
            input_data={
                "query": "Create an executive summary",
                "format": "executive",
                "length": SummaryLength.LONG.value,
            },
            context=[content],
        )
        return result.get("summary", "")
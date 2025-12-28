"""SQL Generator agent for converting natural language to SQL queries."""

from typing import Dict, Any, List
from enum import Enum

from src.agents.base import BaseAgent


class SQLDialect(str, Enum):
    """Supported SQL dialects."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MSSQL = "mssql"


class SQLGeneratorAgent(BaseAgent):
    """Agent for generating SQL queries from natural language."""

    name = "sql_generator"
    description = "Converts natural language questions to SQL queries"

    def __init__(self, dialect: SQLDialect = SQLDialect.POSTGRESQL, **kwargs):
        """Initialize the SQL generator agent.

        Args:
            dialect: SQL dialect to generate for.
        """
        super().__init__(temperature=0.1, max_tokens=1000, **kwargs)
        self.dialect = dialect

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for SQL generation."""
        return f"""You are an expert SQL query generator. Your task is to convert natural language questions into valid {self.dialect.value} SQL queries.

Follow these rules:
1. **Syntax**: Generate only valid {self.dialect.value} SQL syntax
2. **Safety**: Never generate DELETE, DROP, TRUNCATE, or UPDATE statements unless explicitly requested
3. **Clarity**: Add comments explaining complex query logic
4. **Performance**: Consider query performance and use appropriate indexes
5. **Best Practices**:
   - Use explicit column names instead of SELECT *
   - Use table aliases for readability
   - Use parameterized queries where applicable (show placeholders like $1 or ?)
   - Add appropriate WHERE clauses to limit results

Output format:
1. First, provide the SQL query in a code block
2. Then, explain what the query does
3. Note any assumptions made about the schema"""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Generate SQL from natural language.

        Args:
            input_data: Contains 'query' with the natural language question.
            context: Optional schema information.

        Returns:
            Dictionary with the generated SQL and explanation.
        """
        query = input_data.get("query", "")
        schema = input_data.get("schema", "")
        tables = input_data.get("tables", [])
        dialect = input_data.get("dialect", self.dialect.value)

        if not query:
            return {
                "sql": "",
                "error": "No query provided",
            }

        # Build the generation prompt
        prompt = self._build_generation_prompt(query, schema, tables)

        # Generate SQL
        response = await self.generate_response(prompt)

        # Parse the response
        sql_query, explanation = self._parse_response(response)

        return {
            "sql": sql_query,
            "explanation": explanation,
            "dialect": dialect,
            "original_query": query,
        }

    def _build_generation_prompt(
        self,
        query: str,
        schema: str,
        tables: List[str],
    ) -> str:
        """Build the SQL generation prompt.

        Args:
            query: Natural language query.
            schema: Database schema information.
            tables: List of available tables.

        Returns:
            The formatted prompt.
        """
        schema_section = ""
        if schema:
            schema_section = f"""
Database Schema:
```sql
{schema}
```
"""
        elif tables:
            schema_section = f"""
Available tables: {', '.join(tables)}
"""

        return f"""Convert the following natural language question to a {self.dialect.value} SQL query.
{schema_section}
Question: {query}

Generate the SQL query with explanations."""

    def _parse_response(self, response: str) -> tuple[str, str]:
        """Parse the LLM response to extract SQL and explanation.

        Args:
            response: The LLM response.

        Returns:
            Tuple of (sql_query, explanation).
        """
        sql_query = ""
        explanation = response

        # Try to extract SQL from code blocks
        if "```sql" in response:
            parts = response.split("```sql")
            if len(parts) > 1:
                sql_part = parts[1].split("```")[0]
                sql_query = sql_part.strip()
                # Get explanation from remaining text
                remaining_parts = response.split("```")
                if len(remaining_parts) > 2:
                    explanation = remaining_parts[-1].strip()
        elif "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                sql_query = parts[1].strip()
                if len(parts) > 2:
                    explanation = parts[-1].strip()
        else:
            # Try to identify SQL by keywords
            lines = response.split("\n")
            sql_lines = []
            explanation_lines = []
            in_sql = False
            
            for line in lines:
                upper_line = line.upper().strip()
                if any(kw in upper_line for kw in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "WITH"]):
                    in_sql = True
                if in_sql:
                    if line.strip().endswith(";"):
                        sql_lines.append(line)
                        in_sql = False
                    else:
                        sql_lines.append(line)
                else:
                    explanation_lines.append(line)
            
            if sql_lines:
                sql_query = "\n".join(sql_lines)
                explanation = "\n".join(explanation_lines)

        return sql_query, explanation

    async def generate_select(
        self,
        table: str,
        columns: List[str] | None = None,
        conditions: str | None = None,
    ) -> str:
        """Generate a simple SELECT query.

        Args:
            table: Table name.
            columns: List of columns to select.
            conditions: WHERE conditions in natural language.

        Returns:
            Generated SQL query.
        """
        cols = ", ".join(columns) if columns else "*"
        query = f"Select {cols} from {table}"
        if conditions:
            query += f" where {conditions}"

        result = await self.execute(input_data={"query": query})
        return result.get("sql", "")

    async def generate_with_schema(
        self,
        query: str,
        schema: str,
    ) -> Dict[str, Any]:
        """Generate SQL with explicit schema information.

        Args:
            query: Natural language query.
            schema: Database schema definition.

        Returns:
            Dictionary with SQL and explanation.
        """
        return await self.execute(
            input_data={"query": query, "schema": schema}
        )

    def set_dialect(self, dialect: SQLDialect) -> None:
        """Change the SQL dialect.

        Args:
            dialect: New SQL dialect to use.
        """
        self.dialect = dialect
# Claude Code MCP Integration

## Setting Up the MCP Server

When working on Serena in Claude Code, enable the MCP server for language-aware tooling:

1. **Start the server** in a terminal:
   ```bash
   uv run serena-mcp-server
   ```

2. **Configure Claude Code** to use Serena's MCP tools by adding to `.claude/mcp.json`:
   ```json
   {
     "mcp_servers": {
       "serena": {
         "command": "uv",
         "args": ["run", "serena-mcp-server"]
       }
     }
   }
   ```

3. **Activate the project** so Serena knows the project context:
   - Serena auto-detects projects at startup, or
   - Explicitly activate via: `uv run serena-cli activate`

## When to Use Serena Tools vs Built-in Tools

**Prefer Serena MCP tools for:**
- **Symbol navigation & finding** - Use Serena's symbol tools for cross-file refactoring, finding def>
- **Code editing with context** - Use Serena's symbol editing tools when modifications need language->
- **Project-aware search** - Use Serena's file/symbol search for language-aware queries
- **Memory persistence** - Use Serena's memory tools to store project knowledge across sessions

**Built-in Claude Code tools are appropriate for:**
- **Quick reads** of config files or documentation
- **One-off string searches** in non-code files (logs, configs, markdown)
- **Fast exploration** of project structure before Serena is fully initialized
- **External files** outside the project (system files, temporary locations)

**Example workflow:**
- Starting work: use built-in Grep to quickly scan for a function name
- Modifying code: switch to Serena's symbol tools for precise, cross-file refactoring
- Documenting findings: use Serena's memory system to persist insights for future sessions

## Project Activation
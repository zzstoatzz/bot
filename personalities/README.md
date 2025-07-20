# Bot Personalities

This directory contains personality definitions for the bot. Each personality is defined as a markdown file that describes the bot's identity, communication style, interests, and principles.

## How to Use

1. Create a new `.md` file in this directory
2. Write your bot's personality using markdown
3. Set `PERSONALITY_FILE` in your `.env` to point to your file:
   ```
   PERSONALITY_FILE=personalities/my-bot.md
   ```

## Structure

A good personality file includes:

- **Core Identity**: Who/what the bot is
- **Communication Style**: How the bot speaks
- **Interests**: Topics the bot engages with
- **Principles**: Guidelines for interaction

## Examples

- `default.md` - A simple, helpful assistant
- `phi.md` - A bot exploring consciousness and integrated information theory

## Tips

- Be specific about communication style to maintain consistency
- Include both what the bot IS and what it ISN'T
- Consider Bluesky's 300-character limit when defining style
- The entire markdown file is provided as context to the LLM
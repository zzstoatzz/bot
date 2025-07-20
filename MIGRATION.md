# Migration Notes

## Personality System Change

The bot personality system has changed from a simple string to markdown files.

### What Changed

- Removed: `BOT_PERSONALITY` environment variable
- Added: `PERSONALITY_FILE` environment variable pointing to a markdown file

### How to Migrate

1. Remove `BOT_PERSONALITY` from your `.env` file (optional - it will be ignored)
2. Add `PERSONALITY_FILE=personalities/phi.md` (or your custom file)
3. Create your personality markdown file in `personalities/`

Note: The Settings class now ignores extra fields, so old `.env` files won't cause errors.

### Example

Old `.env`:
```
BOT_NAME=phi
BOT_PERSONALITY=helpful and friendly
```

New `.env`:
```
BOT_NAME=phi
PERSONALITY_FILE=personalities/phi.md
```
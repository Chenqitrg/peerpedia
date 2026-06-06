## Need to be careful

- Always check you are in the correct directory.
- When there is new feature, always use /test-driven-development
- Whenever corrected a bug, always add a recursive test
- Always ask more questions before executing
- Some features may seem to be redundant, but may be a plan. Always make sure if you try to simplify it
- Updates always follow README -> API contract -> test -> code.

## All files that should read first

- README.md: a file for current stage and outlook
- docs/DESIGN.en.md: a file that can reconstruct this project
- docs/api-contract.json: API contract

## Session discipline

**After every code change**, clear all caches before verifying:

```bash
lsof -ti:8080 | xargs kill -9 2>/dev/null
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
rm -rf .pytest_cache .mypy_cache .ruff_cache
rm -f .coverage
```

Then restart server and verify.



## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec

# CLAUDE.md

## Read First

- README.md
- docs/DESIGN.en.md
- docs/api-contract.json

---

## Workflow

README → Architecture → API → Test → Code

Bug fix:

1. Reproduce
2. Add regression test
3. Fix
4. Verify

---

## Entity First

Before coding, define:

- Entities
- Relationships
- Lifecycle
- Source of Truth

---

## Storage Rules

Every field must be:

- Primary Data
- Derived Data
- Cache

Do not mix them.

Relationships must be explicitly modeled.

Do not store relationships in JSON.

---

## Source of Truth

Every piece of data has exactly one canonical owner.

Default:

- Git = Source of Truth
- Database = Index / Cache

No dual-write systems without approval.

---

## Architecture Rules

- Modules communicate via Service Interfaces.
- No direct cross-module database access.
- Modules must be replaceable.
- Prefer rewrite over patching complexity.

---

## Stop and Review Before Adding

- New Entity
- New Persistence Layer
- New Cache
- Background Job
- Graph Structure

---

## Final Check

Before coding:

1. What are the entities?
2. How are they related?
3. Who owns the data?
4. What future queries must be supported?
# Feature Specification: Exports

## User Stories

### US1: Responsive exports [P1]

**As a** analyst,
**I want** the exports page to stay usable while a large export runs,
**So that** I can keep working instead of watching a spinner.

**Acceptance Criteria:**
- [ ] The export streams in chunks so the page stays interactive throughout a 50k-row export
- [ ] A running export can be cancelled from the exports page

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Export runs without holding a request thread | Must | US1 |
| R2 | A cancelled export stops writing and releases its handle | Must | US1 |

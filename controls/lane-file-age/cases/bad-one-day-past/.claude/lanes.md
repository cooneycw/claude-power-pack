# Lanes

Reviewed: 2025-12-31

| Lane | Values | How it is exercised |
|---|---|---|
| Checkout | main checkout / linked worktree | tests build both layouts in a temporary repository |
| Environment | dev / prod | the feature flag is read in both; tests set it each way |

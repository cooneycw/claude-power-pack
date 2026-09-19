# Ledger fixture - ROW PRESENT, NOTHING RECORDED

cxpp#227 has a row. Its disposition cell is empty. Under a presence-only rule
the entry is accounted for in the sense that its number appears in a table, and
accounted for in no other sense - which is the absence the ledger exists to
prevent, wearing a row's clothing.

| Entry | Disposition |
|---|---|
| cxpp#189 - native platform delivery | `unresolved` - blocks #1072 |
| cxpp#227 - Nit Store |  |
| cxpp#239 - open PR | `unresolved` - blocks #1076 |

The same out-of-snapshot citation as the other cases, cxpp#287, so this case and
`good-complete` differ in exactly one thing: the emptied disposition cell.

<!-- flow-run n=1 id=71a98a3ad2c64c7a8b45956348ab38e7 -->
## Run 1 - issue #1946 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1946
- Read at:      2026-11-28T04:37:10Z
- updatedAt:    2026-11-27T15:55:23Z   (context only - moves on comments and labels)
- Body digest:  d8445ebada7549b93c23f957c32e636b15bdac49a69f77e360bb4d3f0986723a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1322 of 1322 (cap 16384)

### Body as read
Rechecked main f966fbf5. README.md:15 advertises native vulnerability detection while lib/security/README.md assigns semantic code review to an external native command; CPP supplies deterministic secrets/dependency/policy checks. `.claude/commands/secrets/help.md:24` still advertises an encrypted local provider, but lib/creds/providers/__init__.py exports only env/dotenv/AWS and no cryptography-backed tier. No credential leak or real credential operation is claimed.

The security/secrets command family also embeds the fixed Projects/claude-power-pack runtime location, unlike supported alternate installation roots. Group the user-facing invocation/capability contract: accurately name external dependencies and actual at-rest storage, and resolve the managed CPP checkout through the maintained route. Validate with owned fixtures from an alternate checkout, without reading real credentials. Do not add a provider merely to make the old help true.

Origin: Nit Store #1725 rollover. Original evidence and discovery context:

- Comment 75: https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6820068749
- Comment 86: https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6822437165
- Comment 87: https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6822458029


<!-- end of body -->

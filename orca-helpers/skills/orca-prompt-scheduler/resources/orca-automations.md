# Orca automations reference

The flag reference for `orca automations` lives with the Orca CLI, so it matches the installed version:

```
orca skills get orca-cli --reference references/automations.md
```

`scripts/schedule.py` runs `create`, `edit` and the rollback `remove`, so this skill needs that reference only to read or change an automation by hand.

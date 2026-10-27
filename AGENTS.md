# Independent planner

- All runtime paths and imports must resolve inside this project. Do not depend on the parent workspace's combat code.
- Development: `python -X utf8 -m tools.planner_dev_server --port 8765`.
- Checks: `python -X utf8 -m unittest discover -s tests -v`. Browser tests use isolated storage, never the user's live personal config.
- Default data and personal configuration are separate. Preserve personal weights, ownership, required teams and other settings when updating defaults.
- Maintain `CHANGELOG.md`; accumulate work under Unreleased. Only generate a ZIP on an explicit packaging request; include the full changelog in every ZIP.

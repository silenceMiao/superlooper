# Codex Dispatcher Contract

## Scope

This directory defines the Codex-native adapter that consumes the shared `.superlooper/manifests/<session_id>/execution_manifest.json`. The shared Manifest is the sole source for every node, dependency, and payload. This adapter does not define a separate session state, DAG, report format, quality gate, merge policy, test policy, or apply policy.

## Native dispatch rules

- The parent Codex session uses the native `spawn_agent` tool for currently eligible `mod_*` nodes from the validated shared execution manifest.
- Each child receives only its current node payload, its current module object, and explicitly listed design context. It must not receive the original requirement document, another module payload, or another module output directory.
- The parent session is non-ephemeral and can write required `.superlooper/` contract outputs. Only the shared `task_apply_to_workspace` gate may write target project files, after all preceding shared quality gates pass.
- Each module writes its own output directory and `artifact_manifest.json`. The parent validates artifacts before handing control to the shared code-review gate.
- Quality nodes run only when their dependencies reported by the Manifest and their shared reports have passed. The adapter delegates review, merge, test, apply, session report, and requirement-alignment gates to the core Superlooper protocol.
- The adapter never writes Claude-specific agent registration files or a second DAG representation.

# Debugging Playbook

When debugging Coyote3, start from what the user is experiencing and walk backward through the same runtime path the application follows. Most issues become clear once you inspect context in the right order.

If a page is empty or unexpectedly filtered, check the sample first: assay context, mutable filter state, and any case-specific gene constraints. Then verify assay configuration and panel scope, because those control what sections appear and how filtering is applied. After that, inspect the underlying event records (`variants`, `cnvs`, `transloc`) and confirm the case linkage is correct.

If interpretation looks wrong, check annotation resolution next. Coyote3 can apply existing annotation state automatically by scope, so what users see may reflect historical interpretation context rather than a fresh blank state. If the question is historical reproducibility, inspect report-linked snapshot records rather than current live state.

If report behavior is failing, separate preview and save paths. Preview renders payload without persistence; save requires file write and database writes. Failures commonly come from filesystem permissions, missing report paths, or report metadata persistence issues.

If access behavior is failing, verify authentication state, role/permission assignment, and sample-level access scope. UI hiding alone is not decisive; route-level checks are the true gate.

Automated debugging/test harnesses are still being formalized. Test automation guidance is **coming soon**, so current debugging remains primarily code- and data-driven with targeted manual verification.

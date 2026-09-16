<!-- Fixture core for controls/delegated-core-vendor (issue #1011).
     Deliberately tiny: the control asks whether the gate can tell a matching
     rendered region from a drifted one, not whether it can render the real
     lifecycle. Placeholders here (`{{NAME}}`) sit in the preamble, which is
     never rendered, and that is itself part of what this exercises.
-->
<!-- region: A -->
## Instructions

When the user invokes `/{{DRIVER}}:auto <ISSUE>`, perform these steps in order.

{{STEP_EXTRA}}
Report at the start: `{{DRIVER_TITLE}} Auto`.
<!-- region: B -->
### Step 5: Review

Claude reviews what {{DRIVER_TITLE}} wrote, then runs the quality gates.

# Coyote3 User Guide

## 1. System Overview
Coyote3 is a clinical genomics workflow platform used to review molecular findings and prepare structured, traceable reports. The system is designed for users who need to work with DNA and RNA findings in a controlled environment where data quality, interpretation consistency, and accountability are critical. The main user groups are clinical geneticists, doctors/pathologists, and bioinformatics analysts. Each group interacts with similar core pages, but available actions depend on role permissions.

At a practical level, Coyote3 helps your team move from raw case context to a reviewed report in an organized and repeatable way. It does this by combining data review pages, filtering tools, assay-aware behavior, and report workflows. Instead of manually combining information from disconnected systems, Coyote3 provides a guided workflow where findings can be reviewed, classified, and exported with history tracking.

If you are new to the platform, the most important concept is that Coyote3 is workflow-oriented rather than file-oriented. You do not begin by opening isolated files. You begin with a sample or case context and then move through review pages that are tailored to assay type and role. Your navigation path and available actions are controlled by policy so that sensitive actions are only available to authorized users.

You may also notice that some operations appear strict compared to ordinary web tools. For example, a report may fail to save if a naming conflict exists, or a button may be hidden if your role does not allow that action. These behaviors are intentional. In clinical environments, explicit control is preferable to silent behavior that could introduce uncertainty.

### What Coyote3 is designed to support
- Review of sample-specific findings with assay-aware context.
- Structured interpretation support for variant and fusion workflows.
- Tier-aware prioritization for clinically meaningful review.
- Controlled report preview and save/export flows.
- Traceable action history where required by policy.

### What Coyote3 is not intended to be
- A free-form note-taking system without controlled structure.
- A direct raw database browser.
- A place to bypass role controls for convenience.

### Behind the scenes (simple explanation)
When you click or submit actions in the interface, Coyote3 sends secure requests to a backend service that validates your access and checks data rules before returning results. This means the page does not decide on its own whether an action is allowed; it asks the backend, which applies policy consistently. This approach helps your team get predictable behavior across users and sessions.

---

## 2. Logging In
Login is your entry point to Coyote3 and determines what you can see and do. After successful login, the system loads your role and permission profile to configure the interface for your account.

### Standard login process
1. Open the Coyote3 login page in your approved browser.
2. Enter your username and password.
3. Submit login.
4. On success, you are redirected to the dashboard.

If login succeeds but you do not see expected modules, this usually means your account is authenticated but your role permissions are limited for that module.

### Common login outcomes
- **Successful login**: Dashboard loads and navigation menu becomes available.
- **Credential rejection**: Username/password combination is not valid.
- **Access mismatch**: Login works, but expected pages or buttons are missing.

### Practical checks if login fails
- Confirm username format and password capitalization.
- Confirm you are using the correct environment URL (development vs production).
- Confirm account has not been disabled by administration.
- If repeated failures occur, contact administrator and provide timestamp and username.

### Behind the scenes (simple explanation)
On login, Coyote3 verifies credentials through its secure backend flow. If valid, a session is created so you do not need to re-enter credentials for every click. The session is used to identify your role and to enforce access rules on each request.

### Good practice
Always log out when your session is finished, especially on shared or controlled workstations. This helps prevent accidental unauthorized activity under your account identity.

---

## 3. Navigating the Dashboard
The dashboard is the operational home page for your workflow. It helps you move quickly to sample review, reporting, and governance pages that your role allows.

### Dashboard purpose
The dashboard gives a structured entry to common tasks. Instead of searching manually through URLs, you use dashboard paths to ensure you enter workflows with the right context.

### Typical dashboard elements
- Navigation links to DNA, RNA, report-related, and admin/public sections.
- Summary widgets or quick access elements.
- Recent or relevant operational pointers depending on configuration.

### How to use dashboard effectively
- Start all case work from dashboard where possible.
- Open sample workflows from consistent entry points.
- Use navigation menus rather than browser history when switching domains.

### Why this matters
Consistent entry paths reduce workflow mistakes. If users jump directly between deep pages without context, they may misinterpret whether they are in the correct assay or sample state.

### Behind the scenes (simple explanation)
The dashboard is rendered based on your authenticated user context and permission profile. Links you cannot use are either hidden or blocked when selected. This avoids presenting actions that policy does not allow.

### Common dashboard confusion
- **“I cannot see the same links as a colleague”**: likely role/permission difference.
- **“A link opens but action inside is blocked”**: read permission may exist while write permission is missing.

---

## 4. Viewing Samples
Sample pages are where most users spend their time. A sample context is the central unit for review activity in Coyote3.

### What a sample context means
A sample context includes identifiers, assay information, and associated findings that belong to that sample. It is not just a label; it is the container for review and report workflows.

### Typical sample review steps
1. Open sample list or sample search path.
2. Locate sample by identifier/case context.
3. Open sample details.
4. Move into assay-specific findings views (DNA or RNA).

### Key information to verify first
- Sample identifier
- Case identifier
- Assay or assay group
- Any status or metadata relevant to your review policy

Verifying this early prevents downstream interpretation mistakes caused by context mismatch.

### Working with sample comments and annotations
Depending on role, you may be able to add or review comments. Comments should be concise, factual, and workflow-relevant. Avoid copying large raw text blocks without interpretation purpose.

### Behind the scenes (simple explanation)
When you open a sample page, the UI requests sample context from the backend. The backend checks your access and returns only the structured data needed for that page. If the sample is missing or not accessible, you receive a controlled error response.

### Common sample-view issues
- **Sample not found**: identifier may be wrong or sample may not exist in this environment.
- **Page opens but no findings**: assay-specific data may not be available yet.
- **Edit controls missing**: read permission present, edit permission absent.

---

## 5. Understanding Assay Groups
Assay groups are categories that control how data is interpreted, filtered, and reported. You should always confirm assay group context before drawing conclusions from findings.

### Plain-language definition
An assay group is a predefined testing context that determines what kind of findings are expected and how they should be evaluated. For example, DNA and RNA workflows often use different review logic and output behavior.

### Why assay groups matter in daily work
- They influence which pages and tools appear.
- They affect available filters and thresholds.
- They influence report structure and expectations.

### Practical examples
- A DNA-focused workflow may emphasize variant/CNV/translocation views.
- An RNA-focused workflow may emphasize fusion review and RNA-specific filters.

### Interpreting assay context safely
Do not assume two samples use identical review criteria just because case identifiers look similar. Assay group can materially change interpretation pathways and what counts as an expected finding.

### Behind the scenes (simple explanation)
Coyote3 loads assay-related configuration when you enter sample workflows. The backend uses this configuration to produce the right context and validate allowed operations. This is why the same user may see different fields or actions across different assay groups.

### Common assay misunderstandings
- **“Why is this filter missing on this sample?”**: filter may be assay-specific.
- **“Why is report output layout different?”**: report configuration often depends on assay group.

---

## 6. Interpreting Variant Tiers
Tiering helps organize findings by clinical review priority. The exact clinical meaning of each tier follows your institution’s policy, but Coyote3 provides structure to support consistent application.

### Plain-language definition
A tier is a classification level that helps prioritize findings for review and reporting. It does not replace clinical judgment; it supports it.

### How to use tiers in workflow
- Use tier data to prioritize review sequence.
- Confirm that tier assignment aligns with available evidence and local policy.
- Use comments/classification tools to document reasoning when required.

### Important caution
Tier labels should never be interpreted in isolation. Always evaluate supporting context such as evidence quality, assay context, and case relevance.

### Typical role behavior
- Analysts often prepare tier-aware candidate review sets.
- Clinical users validate or reinterpret findings before final report actions.

### Behind the scenes (simple explanation)
Tier and related context are provided through backend responses. The interface displays them consistently, but final action permissions depend on role policy.

### Common tier issues
- **“Tier appears inconsistent with my expectation”**: review evidence context and policy criteria first.
- **“Cannot apply or remove classification”**: action may require elevated permission.

---

## 7. Filtering and Searching
Filtering and search tools are central to efficient review. They reduce noise and help you focus on relevant findings.

### Filtering goals
- Narrow large finding sets to clinically relevant subsets.
- Apply assay-aware constraints.
- Repeat consistent review patterns across similar cases.

### Search goals
- Locate specific genes, variants, samples, or catalog entries.
- Validate if expected entities are present.

### Recommended filtering workflow
1. Start with broad visibility to understand scope.
2. Apply one filter at a time.
3. Observe result change before adding more filters.
4. Save or document meaningful combinations if policy requires repeatability.

### Avoiding filter misuse
Applying many filters at once can hide relevant findings unintentionally. Use progressive narrowing and confirm counts/results after each adjustment.

### Behind the scenes (simple explanation)
When filters are applied, the UI sends filter parameters to backend endpoints. The backend normalizes input, validates allowed values, then returns filtered data. This ensures filtering behavior is consistent across users.

### Common filtering issues
- **No results after filter changes**: a parameter may be too strict.
- **Unexpected results**: verify assay context and whether a default filter is active.
- **Search returns partial set**: paging or scope settings may limit visible results.

---

## 8. Viewing Audit History
Audit history provides traceability of important actions. It helps teams understand who changed what and when.

### Plain-language definition
Audit history is a protected activity record for significant operations, especially those affecting governance, interpretation, and report lifecycle.

### Why users should care
- Supports accountability and peer review.
- Helps explain why a current state exists.
- Assists with troubleshooting when unexpected changes appear.

### Typical audit fields you may see
- Action type
- Actor (user)
- Target object (sample, report, role, etc.)
- Timestamp
- Outcome (success/failure)

### Role sensitivity
Not all users can view all audit details. Visibility depends on governance policy and role permissions.

### Behind the scenes (simple explanation)
When important actions happen, backend services emit structured audit records. Audit views read these records through permission-gated endpoints.

### Common audit-view questions
- **“Why can I not see audit history?”**: your role may not include audit-view permission.
- **“Why are details limited?”**: policy may restrict sensitive metadata visibility.

---

## 9. Exporting Reports
Report export is a controlled workflow, not a generic file download operation. In Coyote3, report generation and save/export follow validation rules to preserve consistency.

### Typical report workflow
1. Reach report preview from DNA or RNA workflow.
2. Review report content.
3. Execute save/export action if authorized.
4. Verify report appears in history/context list.

### Why preview-first matters
Preview allows users to check context before committing a persistent report artifact. This reduces accidental incorrect report generation.

### Controlled behavior examples
- Save can fail if report identifier/path conflicts with existing file.
- Save can fail if user lacks required report permission.
- Save can fail if required context is incomplete.

### Behind the scenes (simple explanation)
Backend services generate report identifiers, validate output location, save metadata, and attach snapshot context. This sequence ensures the exported artifact is traceable and linked to workflow evidence.

### Good operational practice
- Confirm sample/case identifiers in preview before saving.
- If save fails, do not repeatedly retry without checking error reason.
- Escalate with exact sample/report identifiers and timestamp.

---

## 10. Permission-Based Access Behavior
Coyote3 uses permission-based behavior to keep actions aligned with role responsibilities.

### What this means for users
You may see pages but not be able to perform all actions on them. Read and write privileges are intentionally separated in many workflows.

### Typical behavior patterns
- Button hidden: action not available to your role.
- Button visible but action denied: policy check failed at runtime due to permission detail.
- Page accessible but edits blocked: read permission granted, write permission denied.

### Why this is designed this way
A controlled role model helps reduce accidental high-impact actions and supports accountability. Not all users should have the same mutation capabilities.

### Behind the scenes (simple explanation)
Each backend endpoint checks your role and permission context before performing actions. The UI reflects allowed operations as much as possible, but the backend is the final authority.

### How to request access changes
If workflow duties changed and you need additional access:
1. Contact administrator.
2. Provide specific operation needed.
3. Provide clinical/business justification.

Avoid requesting broad access without scope; least-privilege assignments are preferred.

---

## 11. Troubleshooting Common UI Issues
This section covers frequent issues encountered by clinical and analyst users, with practical resolution steps.

### Issue A: Page loads but data seems incomplete
Possible causes:
- Filter state too restrictive.
- Assay context mismatch.
- Data not yet available in backend.

What to do:
1. Clear or simplify filters.
2. Reconfirm sample and assay context.
3. Refresh page once.
4. If persistent, report sample id and timestamp.

### Issue B: Action fails after clicking save/update
Possible causes:
- Missing permission.
- Validation error.
- Conflict condition (for example, report already exists).

What to do:
1. Capture exact error text.
2. Check if action is allowed for your role.
3. Confirm required fields/context.
4. Escalate with identifiers and error payload.

### Issue C: I can view but cannot edit
This is often expected behavior due to permission separation.

What to do:
- Confirm whether role includes edit permission.
- Request role update if workflow responsibility requires it.

### Issue D: Search is not returning expected items
Possible causes:
- Scope/page constraints.
- Identifier typo.
- Data exists in another environment.

What to do:
1. Verify spelling and case rules.
2. Use broader search terms first.
3. Confirm environment (dev/prod).

### Issue E: Report preview opens but save/export fails
Possible causes:
- Output conflict or naming collision.
- Missing save permission.
- Incomplete backend context for save.

What to do:
1. Confirm preview data context.
2. Retry once only.
3. Capture error and escalate with sample/report ids.

### Issue F: Unexpectedly missing navigation entries
Possible causes:
- Role policy change.
- Session state update after permission changes.

What to do:
1. Re-login.
2. Confirm role assignment with admin.

### Behind the scenes (simple explanation)
Many UI issues are not rendering problems but backend policy/validation outcomes presented through UI messages. This is expected and helps preserve safety.

---

## 12. Simple Glossary in Workflow Context
This glossary explains technical terms in plain language for daily use.

### Sample
The primary unit of analysis. A sample page gathers relevant findings and metadata used for review and reporting.

### Case
A broader clinical context that can include one or more samples.

### Assay group
A test context category (for example DNA-focused or RNA-focused) that controls available filters and workflow behavior.

### Variant
A genomic difference relative to reference sequence, reviewed for potential clinical relevance.

### Fusion
A genomic event involving combination of gene segments, often reviewed in RNA workflows.

### Tier
A priority/classification level used to organize findings according to review policy.

### Audit history
A structured record of significant actions (who did what and when) used for accountability.

### Permission
A rule that allows a specific action (for example view, edit, export).

### Role
A predefined set of permissions associated with a user category.

### Report preview
A non-final rendering step to review output before save/export.

### Report export/save
The controlled action that persists report artifacts and related metadata.

---

## 13. Behind-the-Scenes Behavior You Should Understand
You do not need to know internal code details to use Coyote3 effectively, but understanding high-level behavior helps interpret outcomes.

### Why some actions are slower than others
Some actions require additional policy checks or context assembly before results are returned. This is intentional for consistency and security.

### Why the same user sees different controls in different pages
Permissions can be action-specific and assay-specific. A role may grant broad view access but only limited mutation actions.

### Why strict validation messages appear
Validation ensures structured, consistent data handling. It prevents accidental malformed updates in sensitive workflows.

### Why action history matters
In collaborative clinical work, users need to trace changes and understand current state origin. Audit and report history support that requirement.

---

## 14. Role-Oriented Usage Guidance
### For bioinformatics analysts
- Use filtering and context views to build high-confidence review sets.
- Document interpretation-relevant notes clearly.
- Escalate uncertain cases with identifiers and concise rationale.

### For clinical geneticists and doctors
- Use preview and history views to validate interpretation outputs.
- Review tier context with policy alignment.
- Confirm sign-off readiness before downstream release actions.

### For governance-oriented clinical users
- Coordinate with administrators for role and permission adjustments.
- Use audit visibility tools to review major workflow changes when applicable.

---

## 15. Quality and Safety Practices for Daily Use
- Always verify sample and assay context before interpretation.
- Apply filters incrementally, not all at once.
- Use preview before export in reporting workflows.
- Treat permission denials as policy signals, not UI errors.
- Capture exact identifiers and timestamps when escalating issues.

These habits reduce avoidable workflow errors and improve collaboration quality.

---

## 16. Future Evolution Considerations
Coyote3 will continue evolving to improve workflow clarity, performance, and policy transparency. Likely improvements include richer context help in UI, expanded guided workflows for new users, and stronger role-aware hints around restricted actions. As those improvements are introduced, core principles remain unchanged: controlled access, traceable behavior, and predictable workflow outcomes.

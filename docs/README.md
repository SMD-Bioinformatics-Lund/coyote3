# Coyote3 documentation

Choose the task you need to complete. The guides below give its steps and checks.

## Start with a task

<nav class="docs-task-start" aria-label="Choose a task" markdown="1">

- <span id="review-and-report-a-sample"></span>**[Review and report a sample](user-guide/clinical-review-workflow.md).**
  Find a sample, review its results and save a report.
- <span id="configure-an-assay"></span>**[Set up an assay](administration/assay-setup.md#step-by-step-add-a-new-assay).**
  Prepare its configuration and verify it with a validation sample.
- <span id="install-or-operate-coyote3"></span>**[Install, update or restart Coyote3](deployment/production-deployment.md).**
  Choose the procedure for a new or existing installation.
- <span id="connect-a-pipeline-or-python-application"></span>**[Connect a pipeline](api/authentication.md).**
  Arrange access, prepare sample files and submit them to Coyote3.
- <span id="develop-coyote3"></span>**[Develop Coyote3](getting-started/developer-environment.md).**
  Prepare the development environment, make a change and verify it.
- <span id="investigate-a-problem"></span>**[Get help with a problem](operations/troubleshooting.md).**
  Investigate service failures. For missing sample results, use
  [sample readiness](user-guide/sample-readiness-and-missing-results.md).

</nav>

For evaluation with demonstration data, use the [local quickstart](getting-started/local-quickstart.md).

## Browse the documentation tree

The sidebar puts common actions first. The reference groups contain field
definitions, examples, architecture and other supporting material. Use
[How to use this manual](getting-started/README.md) if you are unsure which kind
of guide you need.

## Frequently used references

<details markdown="1">
<summary>Look up a specific concept or field</summary>

- [Samples and clinical review](user-guide/sample-management.md)
- [Assays, configurations, and gene lists](user-guide/gene-lists-and-assay-context.md)
- [Assay groups](administration/assay-groups.md) and [diagnoses](administration/assay-diagnoses.md)
- [Report preview and save](user-guide/application-guide.md#reports)
- [Raw ingest files and examples](reference/ingest-files/README.md)
- [Clinical concepts and resource identities](reference/clinical-concepts.md): ASP,
  ASPC, ISGL, samples, cases, findings, and reports.
- [Clinical reporting rules](reference/clinical-reporting-rules.md): rule syntax,
  scope selection, validation, and publication.
- [MongoDB collection contracts](reference/mongodb-collections.md): generated field
  definitions used by collection validation.
- [Permission catalog](administration/permission-catalog.md): generated identifiers
  and capabilities installed with the application.
- [Center configuration files](deployment/center-configuration.md): supported
  center-owned files and settings.

</details>

## Documentation sources and site support

Documentation is maintained alongside the application source. Contribution standards,
site configuration, and validation commands are defined in
[Writing documentation](development/writing-documentation.md).

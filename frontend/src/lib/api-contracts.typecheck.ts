/** Compile-time regression checks for the generated HTTP operation contracts. */
import type { ApiOperations } from "./generated/operations.gen";

type Assert<T extends true> = T;
type SamplesQuery = NonNullable<ApiOperations["GET /samples"]["request"]["query"]>;
type SaveReport = ApiOperations["POST /samples/{sample_id}/reports/{report_type}"]["request"];

export type ApiContractChecks = [
  Assert<"GET /invented-resource" extends keyof ApiOperations ? false : true>,
  Assert<string extends SamplesQuery["live_page"] ? false : true>,
  Assert<SaveReport["body"]["preview_fingerprint"] extends string ? true : false>,
  Assert<SaveReport["path"]["sample_id"] extends string ? true : false>,
  Assert<
    ApiOperations["GET /samples"]["response"]["live_samples"] extends unknown[] ? true : false
  >,
];

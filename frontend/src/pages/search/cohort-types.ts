import {
  type GeneKnowledgebasePayload
} from "@/components/knowledgebase/GeneKnowledgebaseSummary";


export type CohortBreakdown = {
  profiled_samples: number;
  finding_samples: number;
  prevalence_percent: number | null;
};

export type AssayCohortRow = CohortBreakdown & {
  asp_id: string;
  display_name: string;
  asp_group?: string;
};

export type RecurrentFinding = {
  identity: string;
  analysis_type: string;
  nomenclature?: string;
  genes: string[];
  gene?: string;
  gene1?: string;
  gene2?: string;
  hgvsp?: string;
  hgvsc?: string;
  genomic?: string;
  transcript?: string;
  sample_count: number;
  observation_count: number;
  latest_tiers: number[];
  historical_tiers: number[];
};

export type SampleFinding = {
  identity: string;
  analysis_type: string;
  nomenclature?: string;
  latest_tier: number;
  tiers: number[];
};

export type CohortSample = {
  sample_name: string;
  asp_id?: string;
  subpanel_id?: string;
  environment?: string;
  sex?: string;
  finding_details: SampleFinding[];
};

export type GeneCohortPayload = {
  query: { resolved_symbol?: string; requested?: string };
  gene?: Record<string, unknown> | null;
  knowledgebase?: GeneKnowledgebasePayload;
  summary: CohortBreakdown & {
    reported_observations: number;
    unique_findings: number;
  };
  denominator: {
    method: string;
    report_scope: "latest" | "historical";
    ready_samples_considered: number;
    samples_excluded_outside_gene_scope: number;
    unrestricted_asp_scope_counts_as_profiled: boolean;
    duplicate_report_observations_removed: number;
  };
  tier_counts: Record<string, number>;
  analysis_type_counts: Record<string, number>;
  assays: AssayCohortRow[];
  sex_distribution: Array<CohortBreakdown & { sex: string }>;
  recurrent_findings: RecurrentFinding[];
  samples: CohortSample[];
  truncated: boolean;
};

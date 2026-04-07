"""Static application constants shared by runtime configuration."""

CONSEQUENCE_TERMS_MAPPER: dict[str, list[str]] = {
    "splicing": [
        "splice_acceptor_variant",
        "splice_donor_variant",
        "splice_region_variant",
    ],
    "stop_gained": ["stop_gained"],
    "frameshift": ["frameshift_variant"],
    "stop_lost": ["stop_lost"],
    "start_lost": ["start_lost"],
    "inframe_indel": [
        "inframe_insertion",
        "inframe_deletion",
    ],
    "missense": [
        "missense_variant",
        "protein_altering_variant",
    ],
    "other_coding": [
        "coding_sequence_variant",
    ],
    "synonymous": [
        "stop_retained_variant",
        "synonymous_variant",
        "start_retained_variant",
        "incomplete_terminal_codon_variant",
    ],
    "transcript_structure": [
        "transcript_ablation",
        "transcript_amplification",
    ],
    "UTR": [
        "5_prime_UTR_variant",
        "3_prime_UTR_variant",
    ],
    "miRNA": [
        "mature_miRNA_variant",
    ],
    "NMD": [
        "NMD_transcript_variant",
    ],
    "non_coding": [
        "non_coding_transcript_exon_variant",
        "non_coding_transcript_variant",
    ],
    "intronic": [
        "intron_variant",
    ],
    "intergenic": [
        "intergenic_variant",
        "downstream_gene_variant",
        "upstream_gene_variant",
    ],
    "regulatory": [
        "regulatory_region_variant",
        "regulatory_region_ablation",
        "regulatory_region_amplification",
        "TFBS_ablation",
        "TFBS_amplification",
        "TF_binding_site_variant",
    ],
    "feature_elon_trunc": [
        "feature_elongation",
        "feature_truncation",
    ],
}

CONTACT_HOURS = ["Mon–Fri: 08:00–16:30", "Closed on public holidays"]

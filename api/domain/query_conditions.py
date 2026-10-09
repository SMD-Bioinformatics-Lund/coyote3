"""Validate and compile bounded finding predicates using an application-owned field catalog."""

from __future__ import annotations

import math
import re
from typing import Any

MAX_DEPTH = 8
MAX_NODES = 100
MAX_LIST_VALUES = 100

# References address the active sample.filters profile, after the normal analysis
# resolver expands selected gene lists and consequence groups. No values are persisted.
FILTER_REFERENCES = {
    "snv": {
        "snvlists": ("filter_genes", "string_list", ["genes", "INFO.selected_CSQ.SYMBOL"]),
        "vep_consequences": (
            "filter_conseq",
            "string_list",
            ["consequence_terms", "INFO.selected_CSQ.Consequence"],
        ),
        "min_depth": ("min_depth", "integer", ["GT.DP"]),
        "min_alt_reads": ("min_alt_reads", "integer", ["GT.VD"]),
        "min_freq": ("min_freq", "number", ["GT.AF"]),
        "max_freq": ("max_freq", "number", ["GT.AF"]),
        "max_popfreq": (
            "max_popfreq",
            "number",
            ["gnomad_frequency", "gnomad_max", "exac_frequency", "thousandG_frequency"],
        ),
    },
    "cnv": {
        "cnvlists": ("filter_genes", "string_list", ["genes.gene"]),
        "min_cnv_size": ("min_cnv_size", "integer", ["size"]),
        "max_cnv_size": ("max_cnv_size", "integer", ["size"]),
        "cnv_loss_cutoff": ("cnv_loss_cutoff", "number", ["ratio"]),
        "cnv_gain_cutoff": ("cnv_gain_cutoff", "number", ["ratio"]),
    },
    "translocation": {
        "fusionlists": (
            "filter_genes",
            "string_list",
            ["INFO.ANN.Gene_Name", "INFO.MANE_ANN.Gene_Name"],
        ),
    },
    "fusion": {
        "fusionlists": ("filter_genes", "string_list", ["gene1", "gene2"]),
        "fusion_callers": ("fusion_callers", "string_list", ["calls.caller"]),
        "fusion_effects": ("fusion_effects", "string_list", ["calls.effect"]),
        "fusion_descriptions": ("fusion_descriptions", "string_list", ["calls.desc"]),
        "min_spanning_reads": ("min_spanning_reads", "integer", ["calls.spanreads"]),
        "min_spanning_pairs": ("min_spanning_pairs", "integer", ["calls.spanpairs"]),
    },
}


def has_filter_references(condition: Any) -> bool:
    """Return whether a condition tree needs the active sample filter context.

    Args:
        condition: JSON-compatible condition tree or subtree.

    Returns:
        True when any operand declares a sample-filter reference.
    """
    if isinstance(condition, dict):
        return condition.get("source") == "sample.filters" or any(
            has_filter_references(v) for v in condition.values()
        )
    return isinstance(condition, list) and any(has_filter_references(v) for v in condition)


def _filter_value(
    value: dict,
    analysis: str,
    field: str,
    operator: str,
    filter_values: dict | None,
    allow_references: bool,
) -> Any:
    """Validate a reference and resolve it from the analysis's prepared filter settings.

    Args:
        value: Exact source/key operand, never arbitrary MongoDB syntax.
        analysis: Finding namespace.
        field: Stored finding path being compared.
        operator: Comparison operator.
        filter_values: Prepared settings for this sample; None for authoring validation.
        allow_references: Permit an unresolved operand only for authoring validation.

    Returns:
        Current resolved filter value, or the reference when validating its structure.

    Raises:
        ValueError: The key, field, operator or required sample context is unavailable.
    """
    if (
        set(value) != {"source", "key"}
        or value.get("source") != "sample.filters"
        or not isinstance(value.get("key"), str)
    ):
        raise ValueError("Expected a registered sample.filters reference")
    entry = FILTER_REFERENCES.get(analysis, {}).get(value["key"])
    if entry is None or field not in entry[2]:
        raise ValueError("Filter reference is not supported for this analysis field")
    permitted = (
        {"in", "nin", "all"}
        if entry[1] == "string_list"
        else {"eq", "ne", "gt", "gte", "lt", "lte"}
    )
    if operator not in permitted:
        raise ValueError("Filter reference is incompatible with this operator")
    if filter_values is None and allow_references:
        return value
    if filter_values is None or entry[0] not in filter_values:
        raise ValueError(f"Sample filter context is required for {value['key']}")
    return filter_values[entry[0]]


OPERATORS = {
    "eq": "Equals",
    "ne": "Does not equal",
    "gt": "Greater than",
    "gte": "At least",
    "lt": "Less than",
    "lte": "At most",
    "in": "Is one of",
    "nin": "Is not one of",
    "exists": "Field exists",
    "type": "Stored BSON type",
    "regex": "Matches pattern",
    "all": "Contains all",
    "size": "Array length equals",
    "mod": "Remainder equals",
    "bitsAllSet": "All selected bits set",
    "bitsAnySet": "Any selected bit set",
    "bitsAllClear": "All selected bits clear",
    "bitsAnyClear": "Any selected bit clear",
}
BSON_TYPES = (
    "double",
    "string",
    "object",
    "array",
    "binData",
    "objectId",
    "bool",
    "date",
    "null",
    "regex",
    "int",
    "timestamp",
    "long",
    "decimal",
    "number",
)


def _catalog() -> dict[str, dict[str, dict[str, Any]]]:
    """Declare reviewed stored fields and value types for each supported finding namespace.

    Returns:
        Analysis to field definitions, including child fields of object arrays.
    """
    definitions = {
        "snv": {
            "string": "CHROM REF ALT ID simple_id variant_class selected_csq_feature dbsnp_id INFO.CLNSIG INFO.CLNREVSTAT INFO.selected_CSQ.SYMBOL INFO.selected_CSQ.Feature INFO.selected_CSQ.BIOTYPE INFO.selected_CSQ.IMPACT INFO.selected_CSQ.HGVSc INFO.selected_CSQ.HGVSp INFO.selected_CSQ.VARIANT_CLASS",
            "integer": "POS GT.DP GT.VD",
            "number": "QUAL gnomad_frequency gnomad_max exac_frequency thousandG_frequency GT.AF",
            "string_list": "FILTER genes transcripts HGVSc HGVSp consequence_terms cosmic_ids pubmed_ids INFO.variant_callers INFO.selected_CSQ.Consequence INFO.selected_CSQ.CLIN_SIG",
            "object_list": "GT",
            "element_string": "GT.GT GT.type",
        },
        "cnv": {
            "string": "chr type genes.gene genes.class genes.cnv_type",
            "integer": "start end size nprobes",
            "number": "ratio",
            "string_list": "callers",
            "object_list": "genes",
        },
        "translocation": {
            "string": "CHROM REF ALT ID INFO.SVTYPE INFO.MATEID INFO.EVENT INFO.SVINSSEQ INFO.MANE_ANN.Gene_Name INFO.MANE_ANN.Gene_ID INFO.MANE_ANN.Annotation_Impact INFO.ANN.Gene_Name INFO.ANN.Gene_ID INFO.ANN.Annotation_Impact GT.PR GT.SR",
            "integer": "POS END INFO.SVINSLEN INFO.SOMATICSCORE INFO.JUNCTION_SOMATICSCORE INFO.BND_DEPTH INFO.MATE_BND_DEPTH",
            "number": "QUAL GT.UR",
            "boolean": "INFO.SOMATIC",
            "string_list": "FILTER FORMAT INFO.PANEL INFO.MANE_ANN.Annotation INFO.ANN.Annotation",
            "object_list": "GT INFO.ANN source_records source_records.GT source_records.INFO.ANN",
        },
        "fusion": {
            "string": "gene1 gene2 genes calls.caller calls.breakpoint1 calls.breakpoint2 calls.effect calls.desc",
            "integer": "calls.selected calls.spanpairs calls.spanreads calls.commonreads",
            "object_list": "calls",
        },
    }
    # Additional typed annotation fields from the finding collection contracts.
    definitions["snv"]["string"] += (
        " INFO.PON_NUM_tnscope INFO.PON_VAFS_tnscope INFO.PON_NUM_vardict INFO.PON_VAFS_vardict INFO.PON_NUM_freebayes INFO.PON_VAFS_freebayes INFO.PON_FFPE_NUM_freebayes INFO.PON_FFPE_VAFS_freebayes INFO.PON_FFPE_NUM_vardict INFO.PON_FFPE_VAFS_vardict INFO.CLNACC INFO.SCOUT_CUSTOM INFO.selected_CSQ.HGNC_ID INFO.selected_CSQ.PolyPhen INFO.selected_CSQ.SIFT INFO.selected_CSQ.ENSP INFO.selected_CSQ.INTRON INFO.selected_CSQ.EXON INFO.selected_CSQ.CANONICAL INFO.selected_CSQ.STRAND INFO.selected_CSQ.CADD_PHRED INFO.selected_CSQ_criteria"
    )
    definitions["translocation"]["string"] += (
        " INFO.ANN_selection_source"
        " source_records.CHROM source_records.ID source_records.REF source_records.ALT source_records.INFO.SVTYPE source_records.INFO.MATEID source_records.INFO.ANN.Gene_Name source_records.INFO.ANN.Gene_ID source_records.GT.PR source_records.GT.SR"
        " INFO.ANN.Allele INFO.ANN.Feature_Type INFO.ANN.Feature_ID INFO.ANN.Transcript_BioType INFO.ANN.Rank INFO.ANN.HGVSc INFO.ANN.HGVSp INFO.ANN.Distance INFO.ANN.ERRORS INFO.ANN.WARNINGS INFO.ANN.INFO INFO.MANE_ANN.Allele INFO.MANE_ANN.Feature_Type INFO.MANE_ANN.Feature_ID INFO.MANE_ANN.Transcript_BioType INFO.MANE_ANN.Rank INFO.MANE_ANN.HGVSc INFO.MANE_ANN.HGVSp INFO.MANE_ANN.Distance INFO.MANE_ANN.ERRORS INFO.MANE_ANN.WARNINGS INFO.MANE_ANN.INFO"
    )
    definitions["translocation"]["integer"] += (
        " source_records.POS source_records.END"
        " INFO.ANN.cDNApos INFO.ANN.cDNAlength INFO.ANN.CDSpos INFO.ANN.CDSlength INFO.ANN.AApos INFO.ANN.AAlength INFO.MANE_ANN.cDNApos INFO.MANE_ANN.cDNAlength INFO.MANE_ANN.CDSpos INFO.MANE_ANN.CDSlength INFO.MANE_ANN.AApos INFO.MANE_ANN.AAlength"
    )
    definitions["translocation"]["number"] += " source_records.QUAL source_records.GT.UR"
    definitions["translocation"]["string_list"] += (
        " source_records.FILTER source_records.INFO.ANN.Annotation"
    )
    result = {}
    for analysis, groups in definitions.items():
        fields = {}
        for kind, names in groups.items():
            kind = "string" if kind == "element_string" else kind
            for path in names.split():
                operators = (
                    ["exists", "type"]
                    if kind == "object_list"
                    else ["eq", "ne", "in", "nin", "exists", "type"]
                )
                if kind in {"number", "integer"}:
                    operators += ["gt", "gte", "lt", "lte", "mod"]
                if kind == "integer":
                    operators += ["bitsAllSet", "bitsAnySet", "bitsAllClear", "bitsAnyClear"]
                if kind in {"string", "string_list"}:
                    operators += ["regex"]
                if kind == "string_list":
                    operators += ["all", "size"]
                if kind == "object_list":
                    operators += ["size"]
                fields[path] = {"path": path, "label": path, "kind": kind, "operators": operators}
        result[analysis] = fields
    return result


FIELD_CATALOG = _catalog()

# Reviewed VCF INFO extras retained by VariantInfoDoc's open INFO contract.
# These existing installed-policy inputs are not arbitrary user-provided paths.
for _path, _kind, _operators in (
    ("INFO.SVTYPE", "string", ["exists", "eq", "ne", "in", "nin"]),
    ("INFO.MYELOID_GERMLINE", "integer", ["exists", "eq", "ne", "in", "nin"]),
):
    FIELD_CATALOG["snv"][_path] = {
        "path": _path,
        "label": _path,
        "kind": _kind,
        "operators": _operators,
    }


def _validate_pattern(pattern: str) -> None:
    """Keep new patterns within a portable subset shared by MongoDB and report evaluation.

    Args:
        pattern: Case-sensitive pattern with at most 200 characters.

    Raises:
        ValueError: Syntax is invalid or uses engine-dependent or nested-repeat constructs.
    """
    if (
        "[[:" in pattern
        or re.search(r"\(\?(?!:)", pattern)
        or re.search(r"\\(?:[A-Za-z0-9])", re.sub(r"\\[tnr]", "", pattern))
        or re.search(r"(?<!\\)\)[*+?{]", pattern)
    ):
        raise ValueError(
            "Patterns cannot use shorthand classes, backreferences, lookarounds, flags or repeated groups"
        )
    # Count unbounded quantifiers outside character classes and escaped literals.
    plain = re.sub(r"\\.|\[(?:\\.|[^\]])*\]", "", pattern)
    if len(re.findall(r"[*+]|\{\d+,\}", plain)) > 1:
        raise ValueError("Patterns allow at most one unbounded quantifier")
    try:
        re.compile(pattern)
    except (re.error, OverflowError) as error:
        raise ValueError("Invalid regular expression") from error


def condition_catalog() -> dict[str, Any]:
    """Return the authoring catalog shared by API validation and the visual builder.

    Returns:
        Fields by analysis, operator labels, BSON type choices and complexity limits.
    """
    return {
        "filter_references": {
            analysis: [
                {"key": key, "kind": spec[1], "fields": spec[2]} for key, spec in refs.items()
            ]
            for analysis, refs in FILTER_REFERENCES.items()
        },
        "fields": {
            analysis: [
                {
                    **field,
                    "filter_references": [
                        {
                            "key": key,
                            "kind": spec[1],
                            "path": f"sample.filters.<intent>.{analysis}.{key}",
                        }
                        for key, spec in FILTER_REFERENCES[analysis].items()
                        if field["path"] in spec[2]
                    ],
                }
                for field in fields.values()
            ]
            for analysis, fields in FIELD_CATALOG.items()
        },
        "operators": OPERATORS,
        "bson_types": list(BSON_TYPES),
        "max_depth": MAX_DEPTH,
        "max_nodes": MAX_NODES,
        "max_list_values": MAX_LIST_VALUES,
    }


def _scalar(value: Any, kind: str) -> bool:
    """Check an exact literal type without coercing strings or booleans to numbers.

    Args:
        value: JSON literal to inspect.
        kind: Application field type; string_list compares individual text elements.

    Returns:
        True for a finite scalar compatible with the field.
    """
    if kind in {"string", "string_list"}:
        return isinstance(value, str) and len(value) <= 1000 and "\x00" not in value
    if kind == "boolean":
        return type(value) is bool
    if kind == "integer":
        return type(value) is int and -(2**63) <= value < 2**63
    return type(value) in {int, float} and abs(value) < 2**63 and math.isfinite(value)


def compile_condition(
    condition: Any,
    analysis: str,
    *,
    filter_values: dict | None = None,
    allow_references: bool = False,
) -> dict[str, Any]:
    """Validate a condition tree and compile only approved MongoDB match predicates.

    Args:
        condition: Predicate, all/any/nor group, not node or object-array elem_match node.
        analysis: snv, cnv, translocation or fusion; selects the stored-field catalog.
        filter_values: Runtime settings resolved for the current sample and analysis.
        allow_references: Validate unresolved references without execution; authoring only.

    Returns:
        MongoDB predicate to combine inside the existing sample-scoped query.
        With allow_references and no filter_values, references remain symbolic;
        that authoring template must not be sent to MongoDB for execution.

    Raises:
        ValueError: Fields, operators, values, node shapes or complexity are unsupported.
    """
    if analysis not in FIELD_CATALOG:
        raise ValueError("Unsupported condition analysis")
    count = 0

    def visit(node: Any, depth: int, prefix: str = "") -> dict[str, Any]:
        """Compile one bounded node, restricting element children to their array.

        Args:
            node: Untrusted condition mapping.
            depth: Root-based nesting depth.
            prefix: Full array path whose element fields are in scope.

        Returns:
            Compiled predicate with relative paths inside an element match.

        Raises:
            ValueError: The condition does not satisfy its shape or field contract.
        """
        nonlocal count
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES:
            raise ValueError(f"Conditions allow at most {MAX_DEPTH} levels and {MAX_NODES} nodes")
        if not isinstance(node, dict):
            raise ValueError("Each condition must be an object")
        kind = node.get("type")
        if not isinstance(kind, str):
            raise ValueError("Condition type must be text")
        if kind in {"all", "any", "nor"}:
            children = node.get("children")
            if set(node) != {"type", "children"} or not isinstance(children, list) or not children:
                raise ValueError("Logical groups require a nonempty children list")
            return {
                {"all": "$and", "any": "$or", "nor": "$nor"}[kind]: [
                    visit(child, depth + 1, prefix) for child in children
                ]
            }
        if kind == "not":
            if set(node) != {"type", "child"}:
                raise ValueError("NOT requires exactly one child")
            return {"$nor": [visit(node["child"], depth + 1, prefix)]}
        field = node.get("field")
        if not isinstance(field, str) or field not in FIELD_CATALOG[analysis]:
            raise ValueError(f"Unknown {analysis} field: {field}")
        if prefix and not field.startswith(prefix + "."):
            raise ValueError("Element conditions must use fields inside the selected array")
        definition = FIELD_CATALOG[analysis][field]
        path = field[len(prefix) + 1 :] if prefix else field
        if kind == "elem_match":
            if set(node) != {"type", "field", "condition"} or definition["kind"] != "object_list":
                raise ValueError("Element matching requires an object-array field and condition")
            return {path: {"$elemMatch": visit(node["condition"], depth + 1, field)}}
        if kind != "predicate" or set(node) != {"type", "field", "operator", "value"}:
            raise ValueError("Predicates require type, field, operator and value only")
        operator, value = node["operator"], node["value"]
        if operator not in definition["operators"]:
            raise ValueError(f"Operator {operator} is not supported for {field}")
        value_kind = definition["kind"]
        referenced = isinstance(value, dict)
        if referenced:
            value = _filter_value(value, analysis, field, operator, filter_values, allow_references)
            if isinstance(value, dict):
                if filter_values is not None:
                    raise ValueError("Resolved filter values must be typed scalars or lists")
                return {path: {f"${operator}": value}}
        valid = False
        if operator == "exists":
            valid = type(value) is bool
        elif operator == "type":
            valid = isinstance(value, str) and value in BSON_TYPES
        elif operator == "size":
            valid = type(value) is int and 0 <= value < 2**31
        elif operator.startswith("bits"):
            valid = (
                isinstance(value, list)
                and 0 < len(value) <= 64
                and all(type(v) is int and 0 <= v <= 63 for v in value)
            )
        elif operator == "mod":
            valid = (
                isinstance(value, list)
                and len(value) == 2
                and all(_scalar(v, "integer") for v in value)
                and value[0] != 0
            )
        elif operator in {"in", "nin", "all"}:
            valid = (
                isinstance(value, list)
                and (0 <= len(value) <= 100000 if referenced else 0 < len(value) <= MAX_LIST_VALUES)
                and all(_scalar(v, value_kind) for v in value)
            )
        elif operator == "regex":
            valid = isinstance(value, str) and 0 < len(value) <= 200
            if valid:
                _validate_pattern(value)
        else:
            valid = (value is None and operator in {"eq", "ne"}) or _scalar(value, value_kind)
        if not valid:
            raise ValueError(f"Invalid {operator} value for {field} ({value_kind})")
        return {path: {f"${operator}": value}}

    return visit(condition, 1)


def matches_condition(
    condition: dict[str, Any],
    analysis: str,
    document: dict[str, Any],
    *,
    filter_values: dict | None = None,
) -> bool:
    """Evaluate supported predicates for in-memory report filtering and synthetic examples.

    Args:
        condition: Validated authoring tree, validated again before evaluation.
        analysis: Finding namespace selecting the field catalog.
        document: Finding or synthetic JSON record; no database access occurs.
        filter_values: Runtime settings for reference operands; required when present.

    Returns:
        Whether the record satisfies the tree, including missing-field and array semantics.

    Raises:
        ValueError: The condition fails the same validation used by query compilation.
    """
    compile_condition(condition, analysis, filter_values=filter_values)
    missing = object()

    def values(item: Any, parts: list[str]) -> list[Any]:
        """Resolve a dotted path through objects and arrays, retaining absent-field markers.

        Args:
            item: Current record, object or array.
            parts: Remaining field path components.

        Returns:
            Terminal values; arrays stay intact until the operator selects their elements.
        """
        if not parts:
            return [item]
        if isinstance(item, list):
            return [value for entry in item for value in values(entry, parts)] or [missing]
        if not isinstance(item, dict) or parts[0] not in item:
            return [missing]
        return values(item[parts[0]], parts[1:])

    def equal(actual: Any, expected: Any) -> bool:
        """Compare Mongo-style JSON scalars while distinguishing booleans from numbers.

        Args:
            actual: Stored value, possibly missing.
            expected: Validated scalar query value.

        Returns:
            Scalar equality; an absent field equals null for query matching.
        """
        if actual is missing:
            return expected is None
        if isinstance(actual, bool) != isinstance(expected, bool):
            return False
        return actual == expected

    def bson_type(value: Any, requested: str) -> bool:
        """Recognize BSON-compatible value types in stored records or JSON examples.

        Args:
            value: Terminal stored value.
            requested: Catalog-approved BSON type alias.

        Returns:
            Whether the value has the requested type, including the numeric umbrella.
        """
        name = type(value).__name__
        aliases = {
            "str": "string",
            "bool": "bool",
            "float": "double",
            "dict": "object",
            "list": "array",
            "NoneType": "null",
            "datetime": "date",
            "ObjectId": "objectId",
            "Decimal128": "decimal",
            "Int64": "long",
            "bytes": "binData",
            "Binary": "binData",
            "Timestamp": "timestamp",
            "Regex": "regex",
            "Pattern": "regex",
        }
        actual = (
            ("int" if -(2**31) <= value < 2**31 else "long")
            if type(value) is int
            else aliases.get(name)
        )
        return (
            actual in {"int", "long", "double", "decimal"}
            if requested == "number"
            else actual == requested
        )

    def visit(node: dict, record: dict, prefix: str = "") -> bool:
        """Evaluate a node against a whole finding or one selected object-array element.

        Args:
            node: Validated condition node.
            record: Finding or object-array member.
            prefix: Full path stripped from fields inside an element match.

        Returns:
            Logical result with MongoDB scalar-array matching and type bracketing.
        """
        kind = node["type"]
        if kind == "all":
            return all(visit(child, record, prefix) for child in node["children"])
        if kind in {"any", "nor"}:
            matched = any(visit(child, record, prefix) for child in node["children"])
            return not matched if kind == "nor" else matched
        if kind == "not":
            return not visit(node["child"], record, prefix)
        field = node["field"]
        path = field[len(prefix) + 1 :] if prefix else field
        actual = values(record, path.split("."))
        if kind == "elem_match":
            return any(
                visit(node["condition"], entry, field)
                for array in actual
                if isinstance(array, list)
                for entry in array
                if isinstance(entry, dict)
            )
        operator, expected = node["operator"], node["value"]
        if isinstance(expected, dict):
            expected = _filter_value(expected, analysis, field, operator, filter_values, False)
        flattened = [
            entry for item in actual for entry in (item if isinstance(item, list) else [item])
        ]
        if operator == "exists":
            return any(item is not missing for item in actual) == expected
        if operator == "type":
            return any(
                bson_type(item, expected) for item in [*actual, *flattened] if item is not missing
            )
        if operator == "size":
            return any(isinstance(item, list) and len(item) == expected for item in actual)
        if operator == "all":
            if not expected:
                return False
            return any(
                isinstance(item, list)
                and all(any(equal(entry, wanted) for entry in item) for wanted in expected)
                for item in actual
            )
        if operator in {"eq", "ne", "in", "nin"}:
            wanted = expected if operator in {"in", "nin"} else [expected]
            matched = any(equal(item, value) for item in flattened for value in wanted)
            return not matched if operator in {"ne", "nin"} else matched
        for item in flattened:
            if operator == "regex":
                if isinstance(item, str) and re.search(expected, item):
                    return True
                continue
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                continue
            if operator == "mod":
                if isinstance(item, int):
                    remainder = abs(item) % abs(expected[0])
                    if item < 0:
                        remainder = -remainder
                elif math.isfinite(item):
                    remainder = math.fmod(item, expected[0])
                else:
                    continue
                if remainder == expected[1]:
                    return True
            if operator.startswith("bits") and isinstance(item, int):
                bits = [bool(item & (1 << bit)) for bit in expected]
                if {
                    "bitsAllSet": all(bits),
                    "bitsAnySet": any(bits),
                    "bitsAllClear": not any(bits),
                    "bitsAnyClear": not all(bits),
                }[operator]:
                    return True
            if (
                operator in {"gt", "gte", "lt", "lte"}
                and {
                    "gt": item > expected,
                    "gte": item >= expected,
                    "lt": item < expected,
                    "lte": item <= expected,
                }[operator]
            ):
                return True
        return False

    return visit(condition, document)

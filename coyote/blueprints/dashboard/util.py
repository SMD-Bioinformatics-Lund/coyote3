from functools import lru_cache
from datetime import datetime
from collections import defaultdict, OrderedDict

import pprint


class DashBoardUtility:
    """
    Utility class for variants blueprint
    """

    @staticmethod
    def convert_annotations_to_hashable(annotations):
        # Helper function to convert datetime to string
        def datetime_to_hashable(dt):
            return dt.isoformat()

        converted = []
        for annotation in annotations:
            annotation["time_created"] = datetime_to_hashable(annotation["time_created"])
            converted.append(frozenset(annotation.items()))
        return tuple(converted)

    @staticmethod
    @lru_cache(maxsize=128)
    def get_classified_variant_stats(annotations: tuple) -> (dict, dict):
        """
        Get classified variant stats
        """
        annotations = [dict(annotation) for annotation in annotations]
        for annotation in annotations:
            annotation["time_created"] = datetime.fromisoformat(annotation["time_created"])

        # Sort annotations by time_created to ensure the latest classification is used
        annotations.sort(key=lambda x: x["time_created"])

        # Create dictionaries to store the latest classifications, assay-specific stats, and gene-specific stats
        latest_classifications = {}
        assay_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        gene_stats = defaultdict(lambda: defaultdict(int))
        gene_class_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        for annotation in annotations:
            key = (annotation["nomenclature"], annotation["variant"])
            if "class" in annotation:
                latest_classifications[key] = annotation["class"]
            else:
                latest_classifications[key] = 0  # Assign 0 for unclassified

            # Update assay-specific stats
            if "assay" in annotation:
                assay = annotation["assay"]
                class_value = annotation.get("class", 0)
                assay_stats[assay][annotation["nomenclature"]][class_value] += 1

            # Update gene-specific stats
            class_value = annotation.get("class", 0)
            if annotation["nomenclature"] == "f":
                gene1 = annotation.get("gene1")
                gene2 = annotation.get("gene2")
                if gene1:
                    gene_stats[gene1][class_value] += 1
                    gene_class_stats[gene1][annotation["nomenclature"]][class_value] += 1
                if gene2:
                    gene_stats[gene2][class_value] += 1
                    gene_class_stats[gene2][annotation["nomenclature"]][class_value] += 1
            else:
                gene = annotation.get("gene")
                if gene:
                    gene_stats[gene][class_value] += 1
                    gene_class_stats[gene][annotation["nomenclature"]][class_value] += 1

        # Create the overall stats dictionary
        stats = defaultdict(lambda: defaultdict(int))

        for (nomenclature, variant), class_value in latest_classifications.items():
            if class_value is not None:
                stats[nomenclature][class_value] += 1

        # Convert defaultdict to a regular dict for pretty printing
        c_nomeclature_stats = {k: dict(v) for k, v in stats.items()}
        if None in c_nomeclature_stats.keys():
            c_nomeclature_stats["no_nomenclature"] = c_nomeclature_stats.pop(None)
        if "f" in c_nomeclature_stats.keys():
            c_nomeclature_stats["fusion"] = c_nomeclature_stats.pop("f")
        if "g" in c_nomeclature_stats.keys():
            c_nomeclature_stats["genomic"] = c_nomeclature_stats.pop("g")
        if "c" in c_nomeclature_stats.keys():
            c_nomeclature_stats["cnv"] = c_nomeclature_stats.pop("c")
        if "p" in c_nomeclature_stats.keys():
            c_nomeclature_stats["protein"] = c_nomeclature_stats.pop("p")

        c_nomeclature_stats = OrderedDict(sorted(c_nomeclature_stats.items()))

        c_assay_stats = {k: {n: dict(c) for n, c in v.items()} for k, v in assay_stats.items()}
        if None in c_assay_stats.keys():
            c_assay_stats["no_assay"] = c_assay_stats.pop(None)

        c_assay_stats = OrderedDict(sorted(c_assay_stats.items()))
        # c_gene_stats = {k: dict(v) for k, v in gene_stats.items()}
        # c_gene_class_stats = { k: {n: dict(c) for n, c in v.items()} for k, v in gene_class_stats.items() }

        return (
            c_nomeclature_stats,
            c_assay_stats,
        )  # c_gene_stats, #c_gene_class_stats

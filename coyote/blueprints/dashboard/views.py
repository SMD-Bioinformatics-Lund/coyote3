from flask import current_app as app, render_template
from flask_login import login_required
from coyote.extensions import store, util
from coyote.blueprints.dashboard import dashboard_bp
import json


@dashboard_bp.route("/", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """
    Dashboard
    """
    total_samples = store.sample_handler.get_all_samples()
    analysed_samples = store.sample_handler.get_all_samples(report=True)
    pending_samples = store.sample_handler.get_all_samples(report=False)
    assay_specific_stats = store.sample_handler.get_assay_specific_sample_stats()

    total_samples_count = len(total_samples)
    analysed_samples_count = len(analysed_samples)
    pending_samples_count = len(pending_samples)

    # Data for the charts
    total_samples_data = {assay: stats["total"] for assay, stats in assay_specific_stats.items()}
    analysed_samples_data = {
        assay: stats["report"] for assay, stats in assay_specific_stats.items()
    }
    pending_samples_data = {
        assay: stats["total"] - stats["report"] for assay, stats in assay_specific_stats.items()
    }

    # Get all classifications
    classified_annotations = util.dashboard.convert_annotations_to_hashable(
        store.annotation_handler.get_all_classified_variants()
    )
    class_stats, assay_class_stats = util.dashboard.get_classified_variant_stats(
        classified_annotations
    )

    return render_template(
        "dashboard.html",
        total_samples=total_samples_count,
        analysed_samples=analysed_samples_count,
        pending_samples=pending_samples_count,
        total_samples_data=total_samples_data,
        analysed_samples_data=analysed_samples_data,
        pending_samples_data=pending_samples_data,
        class_stats_data=json.dumps(class_stats),
        assay_class_stats_data=json.dumps(assay_class_stats),
    )

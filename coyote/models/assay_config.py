from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
from datetime import datetime


class DNAConfig(BaseModel):
    CNV: bool = False
    FUSIONS: Optional[bool] = False
    OTHER: Optional[bool] = False


class AssayConfig(BaseModel):
    assay_name: str
    panel_name: str
    is_active: Optional[bool] = True

    # Frequencies
    default_popfreq: Optional[float] = None
    default_min_freq: Optional[float] = None
    default_max_freq: Optional[float] = None

    # Read thresholds
    default_min_reads: Optional[int] = None
    default_mindepth: Optional[int] = None

    # CNV size thresholds
    default_max_cnv_size: Optional[int] = None
    default_min_cnv_size: Optional[int] = None

    # Coverage warnings
    warn_cov: Optional[int] = None
    error_cov: Optional[int] = None

    # Optional genelist set
    default_genelist_set: Optional[str] = None

    # Nested structures
    DNA: DNAConfig
    verif_samples: Optional[Dict[str, List[int]]] = Field(default_factory=dict)
    query: Optional[Dict[str, Union[str, int, bool, List[Union[str, int]]]]] = Field(
        default_factory=dict
    )

    # Metadata
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[str]
    updated_by: Optional[str]

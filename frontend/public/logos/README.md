# SVG logo assets

These files contain vector paths and shapes, with accessible titles, view boxes
and no embedded raster images or external fonts. Existing files in the parent
directory are retained. The application uses the new SVG filenames for Coyote3
and knowledgebase logos. Modern reports embed the Coyote3 and configured center
logos as data URLs, including when downloaded for offline viewing.

| New asset | Artwork reference |
| --- | --- |
| `coyote-vector.svg` | Coyote3 silhouette, standalone vector paths. |
| `brca-exchange-vector.svg` | [Official BRCA Exchange ribbon](https://github.com/BRCAChallenge/brca-exchange/blob/master/website/js/img/brca_logo.png), reconstructed with polygons and outlined lettering. |
| `civic-vector.svg` | [Official CIViC reference](https://github.com/griffithlab/civic-v2/blob/main/client/src/assets/images/CIViC_logo_for-dark-bg_LG_v5a.png), reconstructed with medical-staff curves, gradients and outlined lettering. |
| `clinpgx-vector.svg` | [Official ClinPGx branding](https://github.com/PharmGKB/pgkb-branding/blob/main/ClinPGx/logo/logo.svg), reconstructed with lettering and helix geometry. |
| `cosmic-vector.svg` | [Official COSMIC banner](https://cancer.sanger.ac.uk/images/banners/cosmic_banner_328x68.png), reconstructed with geometric letterforms and a DNA emblem. |
| `oncokb-vector.svg` | OncoKB wordmark, standalone vector paths. |
| `cpic-vector.svg` | CPIC artwork; original vector geometry retained. |
| `region-skane-vector.svg` | Region Skåne's published mark; original vector geometry retained. |

The four knowledgebase assets above were reconstructed from official web references,
not converted from raster images or copied from the previous traced SVGs. They use
editable polygons, curves, strokes and outlined type, with no external font dependency.
Outlined caption type uses Ubuntu; letterforms and symbols were visually compared
with the official references. These are local reconstructions, not brand-master files.
The COSMIC reference is the current database banner rather than the older combined
COSMIC/Sanger image. References were checked on 2026-10-25.

All SVG canvases are transparent. Dark-mode media rules keep dark lettering
readable under the application's inherited color scheme. Coyote3 and OncoKB retain
their previously reconstructed vector geometry. Legacy raster logo files and the
duplicate CPIC file are no longer distributed.

The server bundles the Coyote3 and Region Skåne vectors. Reports explicitly use
the light color scheme for white paper. Email uses `api/config/assets/coyote-email.png`, rendered from the current
Coyote3 SVG with alpha transparency because email clients have limited SVG support.
The Region Skåne geometry is from the
[attributed vector reference](https://commons.wikimedia.org/wiki/File:Region_Sk%C3%A5ne_logo.svg),
which identifies Region Skåne as its author and links the
[official logo reference](https://www.skane.se/om-region-skane/detta-gor-region-skane/varumarkesmanual/visuell-identitet/logotyp/).
Brand ownership is unchanged; these are vector recreations or normalized copies,
not new designs for the named organizations.

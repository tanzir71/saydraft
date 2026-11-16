# Frozen product captures

These public-fixture captures retain their original app source and producer
hashes in `source.json`. `render-source.py` preserves the exact producer bytes
from `e0b65c7`; its SHA-256 matches the recorded producer. The current renderer
at `site/tools/render_product.py` has since changed for desktop UI v2 and is not
the producer of these historical images. No capture or image hash was changed.

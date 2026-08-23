# Operations

Required repository secrets are `ANTHROPIC_API_KEY` and `AUTOMERGE_TOKEN`; PyPI/TestPyPI
use trusted publishing environments. Enable Actions write permissions, PR creation,
GitHub Pages via Actions, Packages, Releases, and Deployments. Use workflow dispatch for
recovery. Inspect exact run and head SHA before retrying. Never solve a blocked release by
deleting, force-pushing, weakening a gate, or switching production to TestPyPI.

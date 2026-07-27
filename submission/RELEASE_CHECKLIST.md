# Final Release and Submission Checklist

## Repository

- [x] Public source code prepared.
- [x] Apache-2.0 `LICENSE` present at the repository root.
- [x] Complete setup and fixture-testing instructions.
- [x] Verified sample outputs under `examples/`.
- [x] Security boundaries documented.
- [x] One-command showcase included.
- [ ] Confirm the repository **About** section displays the Apache-2.0 licence and hosted website URL.

## Hosted demonstration

- [x] Static responsive demonstration under `docs/`.
- [x] GitHub Pages deployment workflow included.
- [x] Desktop overview screenshot.
- [x] Evidence and repair screenshot.
- [x] Mobile screenshot.
- [x] Accessibility basics: semantic landmarks, keyboard controls, skip link and reduced-motion support.
- [ ] Confirm `https://buriro-ezekia.github.io/modelguard-datahub/` loads in a private browser window.

## Video

- [x] Under-three-minute narration script.
- [x] Shot list with required proof.
- [x] Working-software demonstration recorded at 1080p.
- [x] Public YouTube URL added to `submission/DEVPOST_DRAFT.md` and the README.
- [ ] Verify public playback in a private browser window while signed out of YouTube.

## Devpost

- [x] Project name and tagline prepared.
- [x] Humanised UK English project description prepared.
- [x] Challenge category selected: Production ML Agents.
- [x] DataHub technology list prepared.
- [x] Hosted URL and public repository URL prepared.
- [x] Examples folder linked for generated artefacts.
- [x] Judging guide and testing instructions prepared.
- [x] Public video URL added.
- [ ] Review every required field once more before submission.
- [ ] Submit before the published deadline.

## Final technical verification

```bash
source scripts/bootstrap_codespace.sh
ruff check .
pytest
python scripts/run_showcase.py
python scripts/verify_submission.py
```

Expected showcase summary:

```text
F1: 0.771 -> 0.842
Diagnosis: feature_transformation (1.0)
Repair: validated | guard=True
Publish: GitHub=created DataHub=raised_and_resolved
Repeat: GitHub=noop DataHub=noop
```

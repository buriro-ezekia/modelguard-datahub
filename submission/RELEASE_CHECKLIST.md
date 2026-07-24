# Phase 6 Release and Submission Checklist

## Repository

- [x] Public source code prepared.
- [x] Apache-2.0 `LICENSE` present.
- [x] Complete setup and fixture-testing instructions.
- [x] Verified sample outputs under `examples/`.
- [x] Security boundaries documented.
- [x] One-command showcase included.

## Hosted demonstration

- [x] Static responsive demo under `docs/`.
- [x] GitHub Pages deployment workflow included.
- [x] Desktop overview screenshot.
- [x] Evidence/repair screenshot.
- [x] Mobile screenshot.
- [x] Accessibility basics: semantic landmarks, keyboard controls, skip link and reduced-motion support.
- [ ] After merge: select **Settings → Pages → Source: GitHub Actions** if not already enabled.
- [ ] Confirm `https://buriro-ezekia.github.io/modelguard-datahub/` loads publicly.

## Video

- [x] Under-three-minute narration script.
- [x] Shot list with required proof.
- [ ] Record actual working software at 1080p.
- [ ] Upload publicly to YouTube or Vimeo.
- [ ] Replace `PUBLIC_VIDEO_URL_TO_ADD_AFTER_RECORDING` in `submission/DEVPOST_DRAFT.md`.
- [ ] Verify public playback in an incognito window.

## Devpost

- [x] Project description draft.
- [x] Challenge category selected: Production ML Agents.
- [x] Technology list prepared.
- [x] Hosted URL and public repository URL prepared.
- [x] Judging guide and testing instructions prepared.
- [ ] Add public video URL.
- [ ] Confirm repository About section shows Apache-2.0 licence and hosted demo URL.
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

# Backend Change Notes (a15cd18 -> c629416)

## 1) Routing/Inference Behavior Changes
- Audio upload path was added in API inference routes.
- `/v1/infer` and `/v1/jobs` now detect audio MIME and route audio to `qwen-asr`.
- Batch inference also performs per-file audio detection and mixed routing.

## 2) File Type Policy Changes
- Allowed upload set now includes `audio/mpeg` and `.mp3`.
- Content type resolution is applied more aggressively before routing.

## 3) Runtime/Model Composition Changes
- Local OCR runtime is effectively paddle-centric in current ops/backend wiring.
- Qwen ASR engine is now initialized in app state and consumed by pipeline for audio.
- OCR router fallback complexity was reduced (single local OCR engine shape).

## 4) Pipeline Changes
- Pipeline gained explicit audio branch:
  - audio -> Qwen ASR transcription
  - transcription -> OCRBlock-like unified output
- Existing image/pdf/office flow remains, but step timing/reporting shape is now shared with ASR result.

## 5) Ops Surface Implications
- Ops pages still expose model/server/job/log/playground/settings, but runtime indicators are now mostly paddle-focused.
- Playground server route enforces `engine_hint=auto` in UI/API contract.
- Frontend should present:
  - "auto fixed" engine behavior,
  - audio (mp3) accepted path,
  - resulting `engine_used` can still be `qwen-asr` depending on content type.

## 6) Frontend Rebuild Direction
- Keep SSR routes and existing form actions untouched.
- Rebuild pages around current context keys from `app/ops/routes.py`.
- Explicitly communicate mixed OCR/ASR flow in Playground UX.

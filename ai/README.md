# AI Workspace

`ai` 폴더는 AI 추론 서비스의 단일 작업 공간입니다.

## 현재 구조

- `model/` : 로컬 모델 파일 저장
- `service/` : AI API(backend) + Ops UI(frontend)
- `data/` : DB/테스트 데이터
- `directory.md` : 디렉터리 안내

## 현재 런타임 요약

- 로컬 OCR: `llama.cpp server` + PaddleOCR-VL 모델
- 오디오(`.mp3`) 입력: `Qwen ASR` 분기로 자동 처리
- 엔진 선택:
  - 이미지/PDF/오피스 문서 -> `paddle`
  - 오디오(mp3) -> `qwen-asr`

## Qwen ASR 모델 경로 우선순위

앱 시작 시 아래 순서로 ASR 모델을 결정합니다.

1. `ai/model/Qwen3-ASR-1.7B` (로컬 자동 탐지)
2. `QWEN_ASR_MODEL` 환경변수 경로/모델명
3. 최종 fallback: `Qwen/Qwen3-ASR-1.7B`

추가 ASR 기본값:

- `QWEN_ASR_ENABLE=true`
- `QWEN_ASR_LANGUAGE=Korean`
- `QWEN_ASR_MAX_NEW_TOKENS=96`

## 실행 (Makefile 단일 진입점)

```bash
cd ai
make up-build
```

주요 명령:

```bash
make ps
make logs
make logs-tail
make health
make status
make down
```

기본 접속:

- API: `http://localhost:18080`
- Ops UI: `http://localhost:18080/ops`
- Swagger: `http://localhost:18080/docs`

## 환경파일 선택 우선순위

`ai/Makefile` 기준으로 루트 env를 아래 순서로 선택합니다.

1. `../.env.<COMPUTERNAME>.local`
2. `../.env.local`
3. `../.env`

필요 시 명시적으로 지정:

```bash
ROOT_ENV=../.env.admin.local make up-build
```

## 참고

- 서비스 상세 문서: `ai/service/README.md`

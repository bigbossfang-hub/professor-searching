# Gemini API 설정 가이드

유튜브 스크립트 요약 기능을 사용하기 위해 Google Gemini API 키가 필요합니다.

## 1. Gemini API 키 발급받기

1. **Google AI Studio** 방문
   - https://aistudio.google.com/app/apikey 방문
   - 또는 https://makersuite.google.com/app/apikey

2. **Google 계정으로 로그인**

3. **API 키 생성**
   - "Create API Key" 버튼 클릭
   - 프로젝트 선택 또는 새 프로젝트 생성
   - API 키가 생성되면 복사해서 저장

## 2. 환경 변수 설정

### 방법 1: .env 파일 사용 (권장)

1. 프로젝트 루트 디렉토리에 `.env` 파일 생성

2. 다음 내용 추가:
```
GEMINI_API_KEY=your_actual_api_key_here
```

3. 실제 발급받은 API 키로 `your_actual_api_key_here`를 교체

### 방법 2: Streamlit Secrets 사용 (Streamlit Cloud 배포 시)

1. Streamlit Cloud 대시보드에서 앱 선택
2. Settings > Secrets에 다음 내용 추가:
```toml
GEMINI_API_KEY = "your_actual_api_key_here"
```

### 방법 3: 시스템 환경 변수 설정

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your_actual_api_key_here"
```

**Windows (명령 프롬프트):**
```cmd
set GEMINI_API_KEY=your_actual_api_key_here
```

**Linux/Mac:**
```bash
export GEMINI_API_KEY="your_actual_api_key_here"
```

## 3. 확인

앱을 실행하고 유튜브 링크가 있는 강사를 검색하면, Gemini AI를 사용하여 스크립트가 요약됩니다.

## 주의사항

- API 키는 절대 공개 저장소에 커밋하지 마세요
- `.env` 파일은 `.gitignore`에 추가되어 있어야 합니다
- API 사용량에 따른 비용이 발생할 수 있습니다 (무료 할당량 존재)

## 문제 해결

- **"Gemini API 요약 실패"** 메시지가 나타나는 경우:
  1. API 키가 올바르게 설정되었는지 확인
  2. 인터넷 연결 확인
  3. API 키가 유효한지 확인 (Google AI Studio에서 확인)

- API 키가 없어도 기본 요약 방법으로 동작하지만, Gemini를 사용한 지능형 요약이 제공되지 않습니다.


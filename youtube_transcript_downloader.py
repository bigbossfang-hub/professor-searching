"""
YouTube 동영상 자막 다운로더
YouTube 동영상의 자막(스크립트)을 가져오는 스크립트
최신 youtube-transcript-api v1.2.3 사용
"""

from youtube_transcript_api import YouTubeTranscriptApi
import re
import sys


def extract_video_id(url):
    """
    YouTube URL에서 동영상 ID를 추출합니다.
    
    Args:
        url (str): YouTube 동영상 URL
        
    Returns:
        str: 동영상 ID
    """
    # 다양한 YouTube URL 형식 지원
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # URL이 아닌 직접 ID인 경우
    return url


def get_transcript(video_url, languages=['ko', 'en']):
    """
    YouTube 동영상의 자막을 가져옵니다.
    
    Args:
        video_url (str): YouTube 동영상 URL 또는 ID
        languages (list): 자막 언어 코드 리스트 (기본값: ['ko', 'en'])
        
    Returns:
        tuple: (텍스트 자막, 타임스탬프 포함 자막)
    """
    try:
        # 동영상 ID 추출
        video_id = extract_video_id(video_url)
        print(f"동영상 ID: {video_id}")
        
        # YouTubeTranscriptApi 인스턴스 생성 (v1.2.3 방식)
        ytt_api = YouTubeTranscriptApi()
        
        # 자막 가져오기
        fetched_transcript = ytt_api.fetch(video_id, languages=languages)
        
        print(f"\n'{fetched_transcript.language}' ({fetched_transcript.language_code}) 언어 자막을 가져왔습니다.")
        print(f"자동 생성 여부: {'예' if fetched_transcript.is_generated else '아니오'}")
        
        # 텍스트만 추출
        text_formatted = ""
        for snippet in fetched_transcript:
            text_formatted += snippet.text + "\n"
        
        # 타임스탬프가 포함된 상세 버전 생성
        detailed_transcript = ""
        for snippet in fetched_transcript:
            start_time = snippet.start
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            text = snippet.text
            detailed_transcript += f"[{minutes:02d}:{seconds:02d}] {text}\n"
        
        return text_formatted, detailed_transcript
        
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None


def save_transcript(video_url, output_file='transcript.txt', detailed_file='transcript_detailed.txt'):
    """
    YouTube 동영상의 자막을 파일로 저장합니다.
    
    Args:
        video_url (str): YouTube 동영상 URL
        output_file (str): 출력 파일명 (기본 텍스트)
        detailed_file (str): 상세 출력 파일명 (타임스탬프 포함)
    """
    text_formatted, detailed_transcript = get_transcript(video_url)
    
    if text_formatted:
        # 기본 텍스트 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text_formatted)
        print(f"\n자막이 '{output_file}' 파일로 저장되었습니다.")
        
        # 타임스탬프 포함 상세 버전 저장
        with open(detailed_file, 'w', encoding='utf-8') as f:
            f.write(detailed_transcript)
        print(f"상세 자막이 '{detailed_file}' 파일로 저장되었습니다.")
        
        # 간단한 통계
        word_count = len(text_formatted.split())
        char_count = len(text_formatted)
        print(f"\n통계:")
        print(f"  - 전체 글자 수: {char_count:,}")
        print(f"  - 단어 수: {word_count:,}")
        
        return True
    else:
        print("\n자막을 가져올 수 없습니다.")
        return False


if __name__ == "__main__":
    # 사용 예제
    if len(sys.argv) > 1:
        # 커맨드 라인 인자로 URL 받기
        video_url = sys.argv[1]
    else:
        # 기본 URL (요청하신 URL)
        video_url = "https://youtu.be/7jM1x9QVZ6M?si=x75Frf68wNAY58Ld"
    
    print("=" * 60)
    print("YouTube 자막 다운로더")
    print("=" * 60)
    print(f"\nURL: {video_url}\n")
    
    # 자막 다운로드 및 저장
    save_transcript(video_url)
    
    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


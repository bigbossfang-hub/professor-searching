"""YouTube Transcript API 테스트"""
import youtube_transcript_api

print("youtube_transcript_api 버전:", youtube_transcript_api.__version__)
print("\n사용 가능한 메서드들:")
print(dir(youtube_transcript_api))
print("\nYouTubeTranscriptApi 클래스의 메서드들:")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    print(dir(YouTubeTranscriptApi))
except Exception as e:
    print(f"Import 오류: {e}")

# 실제 사용 테스트
try:
    from youtube_transcript_api.api import YouTubeTranscriptApi as API
    print("\n\napi 모듈에서 import 성공!")
    print(dir(API))
    
    # 테스트
    video_id = "7jM1x9QVZ6M"
    transcript = API.get_transcript(video_id)
    print(f"\n자막 가져오기 성공! 첫 번째 항목: {transcript[0]}")
except Exception as e:
    print(f"\nAPI 테스트 오류: {e}")
    import traceback
    traceback.print_exc()


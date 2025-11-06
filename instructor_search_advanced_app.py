import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
import re
import json
import xml.etree.ElementTree as ET
import google.generativeai as genai
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="강사 고급 검색",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 커스텀 CSS - 차분하고 세련된 색상 테마
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    .main-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
    }
    
    .main-title h1 {
        color: white !important;
        margin: 0 !important;
    }
    
    .main-title p {
        color: rgba(255, 255, 255, 0.95) !important;
        margin-top: 0.5rem !important;
    }
    
    .instructor-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        margin: 1rem 0;
        border-left: 5px solid #667eea;
    }
    
    .instructor-card.selected {
        border-left-color: #f093fb;
        background: #faf0ff;
    }
    
    .info-card {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        margin: 1rem 0;
        border-left: 6px solid #764ba2;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Sheets 연결 함수
@st.cache_resource
def get_google_sheet():
    """구글 시트에 연결"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        SERVICE_ACCOUNT_FILE = os.path.join(current_dir, 'huhsame-service-account-key.json')
        
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )
        
        client = gspread.authorize(credentials)
        SPREADSHEET_ID = '1-EaykQMr06Qm9FWDOJX3CVbAZylGom1G'
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.get_worksheet(0)
        
        return worksheet
    except FileNotFoundError as e:
        return None
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def load_instructor_data():
    """구글 시트에서 강사 데이터 로드"""
    # 방법 1: CSV URL로 공개 데이터 접근 시도
    try:
        SPREADSHEET_ID = '1-EaykQMr06Qm9FWDOJX3CVbAZylGom1G'
        csv_url = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=0'
        df = pd.read_csv(csv_url)
        
        if not df.empty:
            df.columns = df.columns.str.strip()
            return df
    except:
        pass
    
    # 방법 2: 서비스 계정을 통한 gspread 사용
    try:
        worksheet = get_google_sheet()
        if worksheet is not None:
            all_values = worksheet.get_all_values()
            if len(all_values) > 1:
                df = pd.DataFrame(all_values[1:], columns=all_values[0])
                if not df.empty:
                    df.columns = df.columns.str.strip()
                    return df
    except:
        pass
    
    # 방법 3: CSV URL without gid 파라미터 시도
    try:
        SPREADSHEET_ID = '1-EaykQMr06Qm9FWDOJX3CVbAZylGom1G'
        csv_url = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv'
        df = pd.read_csv(csv_url)
        
        if not df.empty:
            df.columns = df.columns.str.strip()
            return df
    except:
        pass
    
    return pd.DataFrame()

def search_instructors(df, query, search_type='all'):
    """
    강사를 검색하는 함수
    search_type: 'name' (강사이름), 'field' (대분야/소분야), 'subject' (강의 과목), 'all' (전체)
    """
    if df.empty or not query:
        return pd.DataFrame()
    
    # 검색할 컬럼 찾기
    name_cols = [col for col in df.columns if '강사' in col and '이름' in col]
    field_cols = [col for col in df.columns if any(x in col for x in ['대분야', '소분야', '분야'])]
    subject_cols = [col for col in df.columns if '강의' in col and '과목' in col]
    
    # 결과 저장
    results = pd.DataFrame()
    
    # 검색 타입에 따라 필터링
    if search_type == 'all' or search_type == 'name':
        for col in name_cols:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            results = pd.concat([results, df[mask]], ignore_index=True)
    
    if search_type == 'all' or search_type == 'field':
        for col in field_cols:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            results = pd.concat([results, df[mask]], ignore_index=True)
    
    if search_type == 'all' or search_type == 'subject':
        for col in subject_cols:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            results = pd.concat([results, df[mask]], ignore_index=True)
    
    # 중복 제거 - 이름과 이메일 주소가 같은 경우 동일인물로 판단
    if not results.empty:
        # 이름과 이메일 컬럼 찾기 (results DataFrame 기준)
        result_name_cols = [col for col in results.columns if '강사' in col and '이름' in col]
        email_cols = [col for col in results.columns if 'e-mail' in col or '이메일' in col]
        
        if result_name_cols and email_cols:
            # 이름과 이메일을 기준으로 중복 제거
            # 첫 번째 기준: 이름 + 이메일이 모두 같은 경우
            name_col = result_name_cols[0]
            email_col = email_cols[0]
            
            # 이름과 이메일이 모두 있는 경우에만 중복 제거
            results = results.drop_duplicates(subset=[name_col, email_col], keep='first')
        else:
            # 이름이나 이메일 정보가 없는 경우 일반 중복 제거
            results = results.drop_duplicates()
    
    return results

def search_naver_person(person_name):
    """
    네이버 인물검색에서 강사 정보를 가져오는 함수
    """
    try:
        # 네이버 인물검색 URL
        encoded_name = urllib.parse.quote(person_name)
        url = f"https://search.naver.com/search.naver?where=nexearch&query={encoded_name}"
        
        # 헤더 설정 (봇 차단 방지)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        # 요청 보내기
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result = {
            'name': person_name,
            'source': '네이버 인물검색',
            'url': url,
            'info': {}
        }
        
        # 다양한 방법으로 인물 정보 찾기
        person_card = None
        
        # 방법 1: people_info 클래스
        person_card = soup.find('div', class_='people_info')
        
        # 방법 2: api_subject_bx 클래스
        if not person_card:
            person_card = soup.find('div', class_='api_subject_bx')
        
        # 방법 3: api_ani_send 클래스
        if not person_card:
            person_card = soup.find('div', class_='api_ani_send')
        
        # 방법 4: 인물 정보가 포함된 섹션 찾기
        if not person_card:
            sections = soup.find_all('section', class_=lambda x: x and 'people' in x.lower())
            if sections:
                person_card = sections[0]
        
        if person_card:
            # 제목/이름 추출
            title = person_card.find('h2', class_='title') or person_card.find('h2')
            if not title:
                title = person_card.find('h3', class_='title') or person_card.find('h3')
            if title:
                title_text = title.get_text(strip=True)
                if title_text:
                    result['info']['이름'] = title_text
            
            # 정보 리스트 추출 (dt/dd 구조)
            info_list = person_card.find('ul', class_='lst_total') or person_card.find('ul')
            if info_list:
                items = info_list.find_all('li')
                for item in items:
                    dt = item.find('dt')
                    dd = item.find('dd')
                    if dt and dd:
                        key = dt.get_text(strip=True).replace(':', '').strip()
                        value = dd.get_text(strip=True)
                        if key and value:
                            result['info'][key] = value
                    else:
                        # dt/dd가 없는 경우 텍스트에서 키-값 추출 시도
                        text = item.get_text(strip=True)
                        if ':' in text:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                if key and value:
                                    result['info'][key] = value
            
            # 설명 정보 추출
            desc = person_card.find('div', class_='dsc') or person_card.find('p', class_='dsc')
            if desc:
                desc_text = desc.get_text(strip=True)
                if desc_text and len(desc_text) > 10:  # 의미있는 설명만
                    result['info']['설명'] = desc_text
        
        # 추가 정보: 바이오그래피 섹션
        bio_section = soup.find('section', class_='api_biography') or soup.find('div', class_='api_biography')
        if bio_section:
            bio_items = bio_section.find_all('li')
            biographies = []
            for item in bio_items:
                bio_text = item.get_text(strip=True)
                if bio_text and len(bio_text) > 5:
                    biographies.append(bio_text)
            if biographies:
                result['info']['약력'] = ' | '.join(biographies[:5])  # 최대 5개만
        
        # 프로필 이미지 찾기
        img = soup.find('img', class_='thumb') or soup.find('img', class_='_img')
        if img:
            img_src = img.get('src') or img.get('data-src')
            if img_src:
                # 상대 경로를 절대 경로로 변환
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    img_src = 'https://search.naver.com' + img_src
                result['info']['이미지'] = img_src
        
        # 유튜브 링크는 네이버에서 찾지 않고 직접 유튜브 검색 사용
        # (여러 링크를 찾기 위해서는 search_youtube_channel 함수 사용)
        # result['info']['유튜브']는 저장하지 않고, 나중에 display 단계에서 search_youtube_channel 호출
        
        # 검색 결과가 있는지 확인
        if len(result['info']) == 0:
            # 간단한 검색 결과 확인
            no_result = soup.find('div', class_='_empty_state')
            if no_result or '검색 결과가 없습니다' in response.text[:5000]:
                return None
            # 정보가 없으면 None 반환하지 않고 빈 정보라도 반환
            return result
        
        return result
        
    except requests.exceptions.RequestException as e:
        # 에러를 표시하지 않고 None 반환 (조용히 실패)
        return None
    except Exception as e:
        # 에러를 표시하지 않고 None 반환 (조용히 실패)
        return None

def filter_relevant_youtube_links(links, person_name, job=None, main_field=None, sub_field=None):
    """
    유튜브 링크의 관련성을 평가하여 필터링하는 함수
    
    Args:
        links: 유튜브 링크 리스트
        person_name: 강사 이름
        job: 직업
        main_field: 대분야
        sub_field: 소분야
        
    Returns:
        관련성이 높은 링크만 필터링한 리스트
    """
    if not links:
        return []
    
    filtered = []
    
    for link in links:
        # 검색 URL이나 채널은 일단 포함
        if link.get('type') in ['search', 'channel']:
            filtered.append(link)
            continue
        
        title = link.get('title', '').lower()
        score = 0
        
        # 1. 강사 이름이 제목에 포함되어 있는지 확인 (가장 중요)
        name_parts = person_name.split()
        name_found = False
        for name_part in name_parts:
            if len(name_part) >= 2 and name_part.lower() in title:
                score += 3
                name_found = True
                break
        
        # 이름이 없으면 기본 점수 낮음
        if not name_found:
            score -= 2
        
        # 2. 직업 키워드가 제목에 포함되어 있는지 확인
        if job:
            job_keywords = ['교수', '박사', '강사', 'ceo', '대표', '이사', '연구원', '교사', '전문가', '컨설턴트']
            for keyword in job_keywords:
                if keyword in str(job).lower() and keyword in title:
                    score += 2
                    break
        
        # 3. 소분야 키워드가 제목에 포함되어 있는지 확인
        if sub_field:
            field_parts = str(sub_field).lower().split()
            for part in field_parts:
                if len(part) >= 2 and part in title:
                    score += 2
                    break
        
        # 4. 대분야 키워드가 제목에 포함되어 있는지 확인
        if main_field and not sub_field:
            field_parts = str(main_field).lower().split()
            for part in field_parts:
                if len(part) >= 2 and part in title:
                    score += 1
                    break
        
        # 5. 강의/강연/세미나 등 교육 관련 키워드가 있으면 가산점
        education_keywords = ['강의', '강연', '세미나', '특강', '강좌', '교육', 'lecture', 'seminar']
        for keyword in education_keywords:
            if keyword in title:
                score += 1
                break
        
        # 6. 관련 없는 키워드가 있으면 감점
        irrelevant_keywords = ['먹방', '일상', 'vlog', '브이로그', '여행', '맛집', '게임', '리뷰', '언박싱']
        for keyword in irrelevant_keywords:
            if keyword in title:
                score -= 3
                break
        
        # 점수가 일정 기준 이상인 링크만 포함 (이름이 있거나 관련 키워드가 충분한 경우)
        if score >= 1:
            link['relevance_score'] = score
            filtered.append(link)
    
    # 원래 순서 유지 (최신순 = 검색 결과 순서)
    # 점수는 필터링 기준으로만 사용하고, 정렬은 원래 순서대로
    filtered.sort(key=lambda x: x.get('order', 0))
    
    return filtered

def search_youtube_channel(person_name, job=None, main_field=None, sub_field=None):
    """
    유튜브에서 인물의 채널/동영상을 검색하는 함수
    여러 유튜브 링크를 리스트로 반환합니다 (최신순).
    
    Args:
        person_name: 검색할 인물 이름
        job: 직업 (예: 교수, 강사, CEO 등)
        main_field: 대분야 (예: 경영, 마케팅 등)
        sub_field: 소분야 (예: 디지털마케팅, 전략경영 등)
    """
    try:
        # 검색 쿼리 생성 (관련 정보 포함)
        search_query_parts = [person_name]
        
        # 직업 추가 (교수, 강사 등 신뢰도 높은 정보)
        if job and pd.notna(job) and job.strip():
            # 직업 중 중요한 키워드만 추출
            job_keywords = ['교수', '박사', '강사', 'CEO', '대표', '이사', '연구원', '교사', '전문가']
            for keyword in job_keywords:
                if keyword in str(job):
                    search_query_parts.append(keyword)
                    break
        
        # 소분야 우선 (더 구체적)
        if sub_field and pd.notna(sub_field) and sub_field.strip():
            # 너무 길지 않은 경우에만 추가 (3단어 이하)
            if len(str(sub_field).split()) <= 3:
                search_query_parts.append(str(sub_field))
        # 대분야 추가 (소분야가 없는 경우)
        elif main_field and pd.notna(main_field) and main_field.strip():
            if len(str(main_field).split()) <= 2:
                search_query_parts.append(str(main_field))
        
        # 최종 검색 쿼리 생성
        search_query = ' '.join(search_query_parts)
        encoded_name = urllib.parse.quote(search_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_name}"
        
        # 웹 스크래핑 시도
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        page_text = response.text
        
        youtube_links = []
        seen_ids = set()
        
        # 방법 1: ytInitialData에서 JSON 파싱
        try:
            # ytInitialData 찾기
            if 'var ytInitialData = ' in page_text:
                start = page_text.find('var ytInitialData = ') + len('var ytInitialData = ')
                end = page_text.find(';</script>', start)
                if end > start:
                    json_str = page_text[start:end]
                    try:
                        data = json.loads(json_str)
                        
                        # 검색 결과에서 동영상 추출
                        contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
                        
                        for content in contents:
                            item_section = content.get('itemSectionRenderer', {})
                            for item in item_section.get('contents', []):
                                # 동영상 아이템
                                if 'videoRenderer' in item:
                                    video = item['videoRenderer']
                                    video_id = video.get('videoId')
                                    if video_id and len(video_id) == 11 and video_id not in seen_ids:
                                        title = video.get('title', {}).get('runs', [{}])[0].get('text', f'동영상 {len(youtube_links) + 1}')
                                        
                                        # 날짜 정보 추출
                                        published_time = None
                                        if 'publishedTimeText' in video:
                                            published_time = video['publishedTimeText'].get('simpleText', '')
                                        elif 'publishedTime' in video:
                                            published_time = video['publishedTime']
                                        
                                        youtube_links.append({
                                            'type': 'video',
                                            'url': f"https://www.youtube.com/watch?v={video_id}",
                                            'id': video_id,
                                            'title': title,
                                            'published': published_time,
                                            'order': len(youtube_links)  # 순서 저장 (최신순)
                                        })
                                        seen_ids.add(video_id)
                                
                                # 채널 아이템
                                elif 'channelRenderer' in item:
                                    channel = item['channelRenderer']
                                    channel_id = channel.get('channelId')
                                    if channel_id and channel_id not in seen_ids:
                                        title = channel.get('title', {}).get('simpleText', f'채널 {len([x for x in youtube_links if x["type"] == "channel"]) + 1}')
                                        youtube_links.append({
                                            'type': 'channel',
                                            'url': f"https://www.youtube.com/channel/{channel_id}",
                                            'id': channel_id,
                                            'title': title,
                                            'published': None,  # 채널은 날짜 정보 없음
                                            'order': len(youtube_links)
                                        })
                                        seen_ids.add(channel_id)
                                
                                # 최대 20개까지
                                if len(youtube_links) >= 20:
                                    break
                            
                            if len(youtube_links) >= 20:
                                break
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            pass
        
        # 방법 2: 정규식으로 비디오 ID 추출 (백업)
        if len(youtube_links) < 5:
            video_patterns = [
                r'"videoId":"([a-zA-Z0-9_-]{11})"',
                r'/watch\?v=([a-zA-Z0-9_-]{11})',
                r'watch\?v=([a-zA-Z0-9_-]{11})',
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, page_text)
                for video_id in matches:
                    if len(video_id) == 11 and video_id not in seen_ids:
                        youtube_links.append({
                            'type': 'video',
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'id': video_id,
                            'title': f"동영상 {len([x for x in youtube_links if x['type'] == 'video']) + 1}",
                            'published': None,  # 백업 방법은 날짜 정보 없음
                            'order': len(youtube_links)
                        })
                        seen_ids.add(video_id)
                        
                        if len(youtube_links) >= 20:
                            break
                
                if len(youtube_links) >= 20:
                    break
            
            # 채널 패턴도 추가
            channel_patterns = [
                r'"channelId":"([^"]+)"',
                r'/channel/([^"/\s]+)',
            ]
            
            for pattern in channel_patterns:
                matches = re.findall(pattern, page_text)
                for channel_id in matches:
                    if channel_id and len(channel_id) > 10 and channel_id not in seen_ids:
                        youtube_links.append({
                            'type': 'channel',
                            'url': f"https://www.youtube.com/channel/{channel_id}",
                            'id': channel_id,
                            'title': f"채널 {len([x for x in youtube_links if x['type'] == 'channel']) + 1}",
                            'published': None,  # 채널은 날짜 정보 없음
                            'order': len(youtube_links)
                        })
                        seen_ids.add(channel_id)
                        
                        if len(youtube_links) >= 20:
                            break
                
                if len(youtube_links) >= 20:
                    break
        
        # 중복 제거 및 순서 유지 (최신순 = 검색 결과 순서)
        unique_links = []
        seen_urls = set()
        for link in youtube_links:
            if link['url'] not in seen_urls:
                unique_links.append(link)
                seen_urls.add(link['url'])
        
        # 관련성 필터링 (강의data에 있는 강사의 경우)
        if job or main_field or sub_field:
            filtered_links = filter_relevant_youtube_links(
                unique_links, 
                person_name, 
                job, 
                main_field, 
                sub_field
            )
            
            # 관련성 있는 링크가 충분히 있는 경우만 반환 (최소 2개 이상)
            if len(filtered_links) >= 2:
                return filtered_links[:15]
            else:
                # 관련성 있는 링크가 너무 적으면 빈 리스트 반환
                return []
        
        # 일반 검색 (네이버, 직접 검색)의 경우 필터링 없이 반환
        if unique_links:
            return unique_links[:15]
        
        # 찾지 못한 경우 검색 URL을 리스트 형태로 반환
        return [{
            'type': 'search',
            'url': search_url,
            'id': 'search',
            'title': '유튜브에서 검색',
            'published': None,
            'order': 0
        }]
        
    except Exception as e:
        # 실패 시 검색 URL 반환
        encoded_name = urllib.parse.quote(person_name)
        return [{
            'type': 'search',
            'url': f"https://www.youtube.com/results?search_query={encoded_name}",
            'id': 'search',
            'title': '유튜브에서 검색',
            'published': None,
            'order': 0
        }]

def extract_video_id_from_url(youtube_url):
    """
    유튜브 URL에서 비디오 ID를 추출하는 함수
    """
    if not youtube_url:
        return None
    
    # 다양한 유튜브 URL 형식 처리
    patterns = [
        r'youtube\.com/watch\?v=([^&]+)',  # watch?v= 형식 (우선)
        r'youtu\.be/([^?]+)',  # youtu.be 형식
        r'youtube\.com/embed/([^?]+)',  # embed 형식
        r'(?:v=|/)([0-9A-Za-z_-]{11})',  # 일반 비디오 ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            video_id = match.group(1)
            # 비디오 ID가 11자인지 확인
            if len(video_id) == 11:
                return video_id
    
    return None

def get_latest_video_from_channel(channel_url):
    """
    채널 URL에서 최신 동영상의 비디오 ID를 가져오는 함수 (개선된 버전)
    """
    if not channel_url:
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        # 채널의 /videos 페이지로 이동
        if '/videos' not in channel_url:
            if channel_url.endswith('/'):
                videos_url = channel_url + 'videos'
            else:
                videos_url = channel_url + '/videos'
        else:
            videos_url = channel_url
        
        response = requests.get(videos_url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        # 여러 방법으로 비디오 ID 찾기
        page_text = response.text
        soup = BeautifulSoup(page_text, 'html.parser')
        
        # 방법 1: JSON 데이터에서 videoId 찾기
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                script_content = script.string
                
                # 패턴 1: "videoId":"xxxxx" 형식
                video_id_patterns = [
                    r'"videoId":"([a-zA-Z0-9_-]{11})"',
                    r'"videoId":\s*"([a-zA-Z0-9_-]{11})"',
                    r'videoId["\s]*[:=]["\s]*([a-zA-Z0-9_-]{11})',
                ]
                
                for pattern in video_id_patterns:
                    matches = re.findall(pattern, script_content)
                    if matches:
                        # 첫 번째 비디오 ID 반환 (보통 최신 동영상)
                        video_id = matches[0]
                        if len(video_id) == 11:
                            return video_id
                
                # 패턴 2: /watch?v=xxxxx 형식
                watch_patterns = [
                    r'/watch\?v=([a-zA-Z0-9_-]{11})',
                    r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                    r'youtu\.be/([a-zA-Z0-9_-]{11})',
                ]
                
                for pattern in watch_patterns:
                    matches = re.findall(pattern, script_content)
                    if matches:
                        video_id = matches[0]
                        if len(video_id) == 11:
                            return video_id
        
        # 방법 2: 페이지 전체 텍스트에서 찾기
        video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
        all_matches = re.findall(video_id_pattern, page_text)
        if all_matches:
            # 중복 제거하고 첫 번째 반환
            unique_ids = list(dict.fromkeys(all_matches))
            for vid_id in unique_ids:
                if len(vid_id) == 11:
                    return vid_id
        
        return None
        
    except Exception as e:
        return None

def get_youtube_transcript(video_id, lang='ko'):
    """
    유튜브 비디오의 자막/스크립트를 가져오는 함수 (youtube-transcript-api v1.2.3 사용)
    """
    if not video_id or len(video_id) != 11:
        return None
    
    try:
        # 방법 1: youtube-transcript-api 라이브러리 사용 (v1.2.3 방식)
        try:
            # YouTubeTranscriptApi 인스턴스 생성
            ytt_api = YouTubeTranscriptApi()
            
            # 한국어 자막 시도
            fetched_transcript = ytt_api.fetch(video_id, languages=['ko', 'ko-KR'])
            if fetched_transcript:
                # 텍스트만 추출해서 합치기 (FetchedTranscript 객체는 iterable)
                transcript_text = ' '.join([snippet.text for snippet in fetched_transcript])
                if len(transcript_text.strip()) > 50:
                    return transcript_text
        except (TranscriptsDisabled, NoTranscriptFound):
            # 한국어 자막이 없으면 영어 시도
            try:
                ytt_api = YouTubeTranscriptApi()
                fetched_transcript = ytt_api.fetch(video_id, languages=['en', 'en-US'])
                if fetched_transcript:
                    transcript_text = ' '.join([snippet.text for snippet in fetched_transcript])
                    if len(transcript_text.strip()) > 50:
                        return transcript_text
            except:
                pass
        except Exception as e:
            pass
        
        # 방법 2: 직접 자막 API 호출 (백업)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/xml,application/xml,*/*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        captions_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang={lang}"
        response = requests.get(captions_url, headers=headers, timeout=15)
        
        if response.status_code == 200 and response.content:
            try:
                root = ET.fromstring(response.content)
                transcript_text = []
                for text_element in root.iter('text'):
                    text = text_element.text
                    if text:
                        transcript_text.append(text.strip())
                
                result = ' '.join(transcript_text)
                if len(result.strip()) > 50:
                    return result
            except:
                pass
        
        # 영어 자막 시도 (백업)
        if lang == 'ko':
            return get_youtube_transcript(video_id, 'en')
        
        return None
        
    except Exception as e:
        return None

def summarize_transcript_with_gemini(transcript, max_length=1000):
    """
    Gemini AI를 사용하여 자막/스크립트를 요약하는 함수 (1000자 내외, 목차별 정리)
    """
    if not transcript:
        return None
    
    # Gemini API 키 가져오기
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        try:
            gemini_api_key = st.secrets['GEMINI_API_KEY']
        except:
            gemini_api_key = None
    
    if not gemini_api_key:
        # API 키가 없으면 기본 요약 방법 사용
        return summarize_transcript_fallback(transcript, max_length)
    
    try:
        # Gemini API 초기화
        genai.configure(api_key=gemini_api_key)
        
        # 모델 선택 (gemini-2.0-flash 우선, 실패 시 다른 모델 시도)
        model = None
        model_names = [
            'gemini-flash-lite-latest',
            'gemini-2.0-flash-exp',  # 최신 Gemini 2.0 Flash 실험 버전
            'gemini-2.0-flash',       # Gemini 2.0 Flash
            'gemini-1.5-flash',       # Gemini 1.5 Flash (빠르고 안정적)
            'gemini-1.5-pro',         # Gemini 1.5 Pro
            'gemini-pro'              # 구버전 Gemini Pro
        ]
        
        last_error = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                # 모델 로딩 성공 시 디버그 정보 (선택사항)
                # st.info(f"✅ Gemini 모델 사용: {model_name}")
                break  # 성공하면 루프 종료
            except Exception as model_err:
                last_error = model_err
                continue  # 다음 모델 시도
        
        if model is None:
            # 모든 모델이 실패한 경우
            if last_error:
                st.warning(f"⚠️ Gemini 모델 로딩 실패: {str(last_error)}")
            return summarize_transcript_fallback(transcript, max_length)
        
        # 프롬프트 생성 (목차별 정리)
        target_length = max_length
        prompt = f"""다음은 유튜브 동영상의 자막/스크립트입니다. 이 내용을 한국어로 정확히 {target_length}자 내외(900-1100자 범위)로 목차별로 정리하여 요약해주세요.

스크립트:
{transcript}

요약할 때 다음 형식과 규칙을 엄격히 지켜주세요:

**형식:**
1. **[주제1]**: 핵심 내용 설명 (2-3문장)
2. **[주제2]**: 핵심 내용 설명 (2-3문장)
3. **[주제3]**: 핵심 내용 설명 (2-3문장)
...

**규칙:**
1. 4-6개의 주요 목차로 구성
2. 각 목차는 핵심 주제를 한 단어나 짧은 구문으로 표현
3. 각 목차별 설명은 2-3문장으로 상세하게
4. 전체 길이는 반드시 {target_length}자 내외(900-1100자 범위)로 작성
5. 가장 중요한 핵심 내용만 포함
6. 불필요한 서문이나 설명 없이 바로 목차 형식으로 작성
7. 구체적인 예시나 중요한 숫자가 있으면 포함

요약 (반드시 900-1100자 범위, 목차별 형식):"""
        
        # 요약 생성
        response = model.generate_content(prompt)
        
        if response and response.text:
            summary = response.text.strip()
            # 요약 길이 조정
            summary_length = len(summary)
            
            # 범위 밖이면 조정 (900-1100자 범위)
            if summary_length > 1100:
                # 너무 길면 앞부분에서 1000자까지 자르기 (문장 단위)
                sentences = re.split(r'([.!?]\s+)', summary)
                result = ""
                for i in range(0, len(sentences), 2):
                    if i + 1 < len(sentences):
                        sentence_pair = sentences[i] + sentences[i+1]
                    else:
                        sentence_pair = sentences[i]
                    
                    if len(result) + len(sentence_pair) <= 1000:
                        result += sentence_pair
                    else:
                        break
                summary = result.strip()
                if len(summary) < 900:
                    # 너무 짧으면 원본에서 더 추가
                    remaining = summary
                    for i in range(len(sentences) - len(result), len(sentences)):
                        if i + 1 < len(sentences):
                            sentence_pair = sentences[i] + sentences[i+1]
                        else:
                            sentence_pair = sentences[i]
                        if len(remaining) + len(sentence_pair) <= 1000:
                            remaining += sentence_pair
                        else:
                            break
                    summary = remaining.strip()
                if len(summary) > 1100:
                    summary = summary[:1000] + "..."
            
            elif summary_length < 800:
                # 너무 짧으면 원본 스크립트에서 더 추가 (Gemini가 충분히 요약하지 않은 경우)
                pass  # 그대로 사용 (Gemini 요약 결과)
            
            return summary
        else:
            return summarize_transcript_fallback(transcript, max_length)
            
    except Exception as e:
        # 에러 발생 시 기본 방법 사용
        st.warning(f"⚠️ Gemini API 요약 실패, 기본 요약 방법 사용: {str(e)}")
        return summarize_transcript_fallback(transcript, max_length)

def summarize_transcript_fallback(transcript, max_length=1000):
    """
    자막/스크립트를 기본 방법으로 요약하는 함수 (Gemini 실패 시 사용)
    900-1100자 범위로 엄격하게 제한
    """
    if not transcript:
        return None
    
    # 목표 길이 범위 설정 (900-1100자)
    target_min = 900
    target_max = 1100
    
    # 길이가 이미 적절하면 그대로 반환
    if target_min <= len(transcript) <= target_max:
        return transcript
    
    # 너무 짧으면 그대로 반환 (요약 불필요)
    if len(transcript) < target_min:
        return transcript
    
    # 문장 단위로 나누기
    sentences = re.split(r'([.!?]\s+)', transcript)
    
    # 첫 부분부터 차례로 더해서 목표 길이 범위까지
    summary = []
    current_length = 0
    
    # 문장과 구분자를 짝으로 처리
    for i in range(0, len(sentences), 2):
        if i < len(sentences):
            sentence = sentences[i].strip()
            if i + 1 < len(sentences):
                separator = sentences[i + 1]
            else:
                separator = ""
            
            if not sentence:
                continue
            
            sentence_with_sep = sentence + separator
            sentence_length = len(sentence_with_sep)
            
            # 목표 범위를 넘지 않으면 추가
            if current_length + sentence_length <= target_max:
                summary.append(sentence_with_sep)
                current_length += sentence_length
            else:
                # 목표 범위에 가까워졌는지 확인
                if current_length >= target_min:
                    break
                # 아직 목표 범위 미만이면 추가 (하지만 최대값 초과하지 않도록)
                if current_length + sentence_length <= target_max:
                    summary.append(sentence_with_sep)
                    current_length += sentence_length
                    break
    
    result = ''.join(summary).strip()
    
    # 최종 길이 확인 및 조정
    if len(result) > target_max:
        # 문장 단위로 자르기
        sentences_result = re.split(r'([.!?]\s+)', result)
        trimmed = ""
        for i in range(0, len(sentences_result), 2):
            if i < len(sentences_result):
                sentence = sentences_result[i]
                if i + 1 < len(sentences_result):
                    separator = sentences_result[i + 1]
                else:
                    separator = ""
                sentence_with_sep = sentence + separator
                
                if len(trimmed) + len(sentence_with_sep) <= target_max:
                    trimmed += sentence_with_sep
                else:
                    break
        result = trimmed.strip()
        if len(result) > target_max:
            result = result[:1000] + "..."
    
    # 최소 길이 확인
    if len(result) < target_min and len(transcript) > target_min:
        # 원본에서 더 가져오기 (단, 최대값 초과하지 않도록)
        remaining_sentences = re.split(r'([.!?]\s+)', transcript[len(''.join(summary)):])
        for i in range(0, len(remaining_sentences), 2):
            if i < len(remaining_sentences):
                sentence = remaining_sentences[i].strip()
                if i + 1 < len(remaining_sentences):
                    separator = remaining_sentences[i + 1]
                else:
                    separator = ""
                
                if not sentence:
                    continue
                
                sentence_with_sep = sentence + separator
                if len(result) + len(sentence_with_sep) <= target_max:
                    result += sentence_with_sep
                else:
                    break
    
    return result

def summarize_transcript(transcript, max_length=1000):
    """
    자막/스크립트를 요약하는 함수 (Gemini 우선 사용, 1000자 내외, 목차별 정리)
    """
    return summarize_transcript_with_gemini(transcript, max_length)

def get_youtube_summary(youtube_url, person_name):
    """
    유튜브 채널/동영상 정보를 가져와서 요약하는 함수
    """
    if not youtube_url or 'youtube.com/results' in youtube_url:
        # 검색 URL인 경우 요약 정보 없음
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        response = requests.get(youtube_url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary = {
            'channel_title': None,
            'description': None,
            'subscriber_count': None,
            'video_count': None,
            'recent_videos': []
        }
        
        # 스크립트 태그에서 JSON 데이터 찾기
        scripts = soup.find_all('script')
        page_data = None
        
        for script in scripts:
            if script.string and ('var ytInitialData' in script.string or 'window["ytInitialData"]' in script.string):
                # 유튜브 초기 데이터 추출 시도
                try:
                    # JSON 데이터 추출
                    script_text = script.string
                    if 'var ytInitialData' in script_text:
                        start_idx = script_text.find('var ytInitialData = ') + len('var ytInitialData = ')
                        end_idx = script_text.find(';</script>', start_idx)
                        if end_idx == -1:
                            end_idx = script_text.find('};', start_idx) + 1
                        if end_idx > start_idx:
                            json_str = script_text[start_idx:end_idx]
                            try:
                                page_data = json.loads(json_str)
                            except:
                                pass
                except:
                    pass
        
        # 채널 제목 찾기
        title = soup.find('meta', property='og:title')
        if title:
            summary['channel_title'] = title.get('content', '')
        
        # 설명 찾기
        desc = soup.find('meta', property='og:description')
        if desc:
            summary['description'] = desc.get('content', '')
        
        # 채널 정보 텍스트에서 구독자 수, 동영상 수 찾기
        if page_data:
            try:
                # 채널 정보 추출 (JSON 구조가 복잡하므로 일반적인 경로 시도)
                channel_info_text = str(page_data)
                # 구독자 수 패턴
                subscriber_pattern = r'(\d+(?:\.\d+)?[만천억개]*)\s*명?\s*구독'
                subscriber_match = re.search(subscriber_pattern, channel_info_text, re.IGNORECASE)
                if subscriber_match:
                    summary['subscriber_count'] = subscriber_match.group(1)
                
                # 동영상 수 패턴
                video_pattern = r'동영상\s*(\d+(?:,\d+)*)'
                video_match = re.search(video_pattern, channel_info_text)
                if video_match:
                    summary['video_count'] = video_match.group(1)
            except:
                pass
        
        # 페이지 텍스트에서 정보 찾기
        page_text = soup.get_text()
        
        # 구독자 수 찾기
        if not summary['subscriber_count']:
            subscriber_patterns = [
                r'구독자\s*(\d+(?:\.\d+)?[만천억]*)\s*명',
                r'(\d+(?:\.\d+)?[만천억]*)\s*구독자',
                r'Subscribers:\s*(\d+(?:,\d+)*)'
            ]
            for pattern in subscriber_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    summary['subscriber_count'] = match.group(1)
                    break
        
        # 동영상 수 찾기
        if not summary['video_count']:
            video_patterns = [
                r'동영상\s*(\d+(?:,\d+)*)\s*개',
                r'(\d+(?:,\d+)*)\s*동영상',
                r'Videos:\s*(\d+(?:,\d+)*)'
            ]
            for pattern in video_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    summary['video_count'] = match.group(1)
                    break
        
        # 최근 동영상 제목 찾기 (간단하게)
        video_titles = []
        # 메타 태그나 제목에서 동영상 정보 찾기
        meta_tags = soup.find_all('meta', {'property': 'og:title'})
        for meta in meta_tags:
            title_text = meta.get('content', '')
            if title_text and title_text != summary['channel_title']:
                video_titles.append(title_text)
                if len(video_titles) >= 3:
                    break
        
        summary['recent_videos'] = video_titles[:3]
        
        # 비디오 URL인 경우 자막/스크립트 가져오기
        video_id = extract_video_id_from_url(youtube_url)
        
        # 비디오 ID가 없으면 채널 URL로 간주하고 최신 동영상 찾기
        if not video_id:
            # 채널 URL인지 확인
            is_channel = any(x in youtube_url for x in ['/channel/', '/c/', '/@', '/user/'])
            if is_channel:
                # 채널에서 최신 동영상 찾기
                video_id = get_latest_video_from_channel(youtube_url)
        
        # 원본 스크립트와 요약 저장
        summary['transcript_raw'] = None
        summary['transcript_summary'] = None
        summary['video_id_used'] = video_id  # 디버깅용
        
        if video_id:
            # 스크립트 가져오기 시도
            try:
                transcript = get_youtube_transcript(video_id)
                if transcript and len(transcript.strip()) > 50:  # 의미있는 스크립트인지 확인
                    # 원본 스크립트 저장 (요약 없이 그대로)
                    summary['transcript_raw'] = transcript
                    # 요약도 생성 (1000자 내외, 목차별 정리)
                    try:
                        summary['transcript_summary'] = summarize_transcript(transcript, max_length=1000)
                    except Exception as sum_err:
                        summary['transcript_summary'] = None
                        summary['error_summary'] = f"요약 실패: {str(sum_err)}"
                else:
                    summary['error_transcript'] = "스크립트가 너무 짧거나 없습니다"
            except Exception as trans_err:
                summary['error_transcript'] = f"스크립트 가져오기 실패: {str(trans_err)}"
        
        return summary
        
    except Exception as e:
        return None

def display_youtube_list_and_summary(youtube_links, person_name, instructor_name):
    """
    유튜브 링크 리스트를 표시하고 선택된 링크의 요약 정보를 표시하는 함수
    """
    if not youtube_links:
        st.markdown("---")
        st.info("💡 관련성이 높은 유튜브 콘텐츠를 찾을 수 없습니다.")
        return
    
    st.markdown("---")
    
    # 디버깅: 찾은 링크 개수 표시
    video_count = len([l for l in youtube_links if l['type'] == 'video'])
    channel_count = len([l for l in youtube_links if l['type'] == 'channel'])
    st.markdown(f"**📺 유튜브 검색 결과:** 동영상 {video_count}개, 채널 {channel_count}개")
    
    # 세션 상태 초기화 (선택된 유튜브 URL 저장용)
    selected_youtube_key = f"selected_youtube_{instructor_name}"
    if selected_youtube_key not in st.session_state:
        st.session_state[selected_youtube_key] = None
    
    # 검색 URL만 있는 경우 (실제 링크를 못 찾음)
    if len(youtube_links) == 1 and youtube_links[0]['type'] == 'search':
        youtube_link = youtube_links[0]
        st.markdown(f"[{youtube_link['title']}]({youtube_link['url']})")
        st.info("💡 유튜브에서 직접 검색해보세요.")
        return
    
    # 유튜브 링크가 1개만 있는 경우
    if len(youtube_links) == 1:
        youtube_link = youtube_links[0]
        st.markdown(f"**제목:** {youtube_link['title']}")
        st.markdown(f"[🔗 링크 열기]({youtube_link['url']})")
        display_youtube_summary(youtube_link['url'], person_name)
        return
    
    # 여러 개의 유튜브 링크가 있는 경우
    st.markdown(f"**📋 총 {len(youtube_links)}개의 링크 (최신순):**")
    st.caption("💡 원하는 동영상을 클릭하면 해당 제목 바로 아래에 스크립트 요약이 표시됩니다")
    
    # 동영상과 채널 분리
    video_links = [link for link in youtube_links if link['type'] == 'video']
    channel_links = [link for link in youtube_links if link['type'] == 'channel']
    
    # 동영상 리스트 (각 동영상 아래에 선택 시 요약 표시)
    if video_links:
        st.markdown(f"### 🎬 동영상 ({len(video_links)}개)")
        for idx, link in enumerate(video_links[:10]):  # 최대 10개
            # 버튼 표시 (날짜 포함)
            display_title = link['title']
            if len(display_title) > 60:
                display_title = display_title[:57] + "..."
            
            # 날짜 정보 추가
            if link.get('published'):
                button_text = f"▶️ {display_title}  📅 {link['published']}"
            else:
                button_text = f"▶️ {display_title}"
            
            button_clicked = st.button(
                button_text, 
                key=f"video_{instructor_name}_{idx}", 
                use_container_width=True
            )
            
            if button_clicked:
                if st.session_state[selected_youtube_key] == link['url']:
                    # 이미 선택된 항목을 다시 클릭하면 선택 취소
                    st.session_state[selected_youtube_key] = None
                else:
                    # 새로운 항목 선택
                    st.session_state[selected_youtube_key] = link['url']
                st.rerun()
            
            # 선택된 동영상이면 바로 아래에 요약 표시
            if st.session_state[selected_youtube_key] == link['url']:
                st.markdown('<div style="background-color: #f0f7ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #667eea; margin: 0.5rem 0 1rem 2rem;">', unsafe_allow_html=True)
                
                st.markdown(f"**✅ 선택된 동영상:** {link['title']}")
                if link.get('published'):
                    st.markdown(f"**📅 게시일:** {link['published']}")
                st.markdown(f"[🔗 유튜브에서 보기]({link['url']})")
                
                # 선택 취소 버튼
                if st.button("❌ 선택 취소", key=f"clear_video_{instructor_name}_{idx}"):
                    st.session_state[selected_youtube_key] = None
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # 요약 정보 표시 (동영상 바로 아래)
                st.markdown('<div style="margin-left: 2rem;">', unsafe_allow_html=True)
                display_youtube_summary(link['url'], person_name)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")
    
    # 채널 리스트 (동영상과 분리)
    if channel_links:
        st.markdown(f"### 📢 채널 ({len(channel_links)}개)")
        for idx, link in enumerate(channel_links[:10]):  # 최대 10개
            # 버튼 표시
            display_title = link['title']
            if len(display_title) > 60:
                display_title = display_title[:57] + "..."
            
            button_clicked = st.button(
                f"📺 {display_title}", 
                key=f"channel_{instructor_name}_{idx}", 
                use_container_width=True
            )
            
            if button_clicked:
                if st.session_state[selected_youtube_key] == link['url']:
                    # 이미 선택된 항목을 다시 클릭하면 선택 취소
                    st.session_state[selected_youtube_key] = None
                else:
                    # 새로운 항목 선택
                    st.session_state[selected_youtube_key] = link['url']
                st.rerun()
            
            # 선택된 채널이면 바로 아래에 요약 표시
            if st.session_state[selected_youtube_key] == link['url']:
                st.markdown('<div style="background-color: #f0f7ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #667eea; margin: 0.5rem 0 1rem 2rem;">', unsafe_allow_html=True)
                
                st.markdown(f"**✅ 선택된 채널:** {link['title']}")
                st.markdown(f"[🔗 유튜브에서 보기]({link['url']})")
                
                # 선택 취소 버튼
                if st.button("❌ 선택 취소", key=f"clear_channel_{instructor_name}_{idx}"):
                    st.session_state[selected_youtube_key] = None
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # 요약 정보 표시 (채널 바로 아래)
                st.markdown('<div style="margin-left: 2rem;">', unsafe_allow_html=True)
                display_youtube_summary(link['url'], person_name)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")

def display_youtube_summary(youtube_url, person_name):
    """
    선택된 유튜브의 요약 정보를 UI에 표시하는 함수
    """
    if not youtube_url:
        return
    
    # 요약 정보 가져오기
    summary_cache_key = f"youtube_summary_{youtube_url}"
    if summary_cache_key not in st.session_state:
        with st.spinner("유튜브 채널 정보 및 스크립트를 불러오는 중..."):
            summary = get_youtube_summary(youtube_url, person_name)
            st.session_state[summary_cache_key] = summary
    else:
        summary = st.session_state[summary_cache_key]
    
    if not summary:
        st.warning("⚠️ 유튜브 정보를 불러올 수 없습니다.")
        return
    
    # 요약 정보를 박스로 표시
    st.markdown('<div style="background-color: #ffffff; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 1rem 0;">', unsafe_allow_html=True)
    
    summary_text = []
    
    if summary.get('channel_title'):
        summary_text.append(f"• **채널명:** {summary['channel_title']}")
    
    if summary.get('subscriber_count'):
        summary_text.append(f"• **구독자 수:** {summary['subscriber_count']}")
    
    if summary.get('video_count'):
        summary_text.append(f"• **동영상 수:** {summary['video_count']}개")
    
    if summary_text:
        st.markdown("**📺 채널 정보:**")
        st.markdown("\n".join(summary_text))
    
    # 주요 내용 표시 (우선순위: 요약 > 설명)
    if summary.get('transcript_summary'):
        # 스크립트 요약이 있으면 표시
        st.markdown("---")
        st.markdown("### 📋 스크립트 요약 (1000자 목차별)")
        st.markdown(summary['transcript_summary'])
        
        # 비디오 ID 표시 (디버깅용)
        if summary.get('video_id_used'):
            st.caption(f"✅ 비디오 ID: {summary['video_id_used']}")
        
        # 원본 스크립트 보기 (접을 수 있게)
        if summary.get('transcript_raw'):
            with st.expander("📝 원본 스크립트 전체 보기"):
                st.text_area("", value=summary['transcript_raw'], height=400, disabled=True, label_visibility="collapsed")
    
    elif summary.get('transcript_raw'):
        # 요약은 없지만 원본 스크립트가 있으면 표시
        st.markdown("---")
        st.markdown(f"**📋 주요 내용 (원본 스크립트):**")
        st.text_area("", value=summary['transcript_raw'], height=300, disabled=True, label_visibility="collapsed")
        if summary.get('video_id_used'):
            st.caption(f"✅ 비디오 ID: {summary['video_id_used']}")
    
    elif summary.get('description'):
        # 스크립트가 없으면 설명을 주요 내용으로 표시
        st.markdown("---")
        desc = summary['description']
        if len(desc) > 1000:
            desc = desc[:1000] + "..."
        st.markdown(f"**📋 주요 내용:**\n\n{desc}")
        
        # 에러 정보 표시 (있는 경우)
        if summary.get('error_transcript'):
            st.info(f"ℹ️ {summary['error_transcript']}")
        if summary.get('video_id_used'):
            st.caption(f"🔍 시도한 비디오 ID: {summary['video_id_used']}")
    
    else:
        # 아무것도 없는 경우
        if summary.get('error_transcript'):
            st.warning(f"⚠️ {summary['error_transcript']}")
        if summary.get('video_id_used'):
            st.info(f"🔍 시도한 비디오 ID: {summary['video_id_used']}")
    
    # 최근 동영상 정보
    if summary.get('recent_videos'):
        st.markdown("---")
        st.markdown("**📹 최근 동영상:**")
        for video in summary['recent_videos'][:3]:
            st.markdown(f"  - {video}")
    
    # 박스 닫기
    st.markdown('</div>', unsafe_allow_html=True)

# Session state 초기화
if 'selected_instructor' not in st.session_state:
    st.session_state.selected_instructor = None
if 'selected_instructor_idx' not in st.session_state:
    st.session_state.selected_instructor_idx = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()
if 'web_search_result' not in st.session_state:
    st.session_state.web_search_result = None
if 'last_search_query' not in st.session_state:
    st.session_state.last_search_query = None
if 'last_search_type' not in st.session_state:
    st.session_state.last_search_type = None

# 메인 UI
st.markdown('<div class="main-title"><h1>🔍 강사 고급 검색 시스템</h1><p>강사이름, 분야, 또는 강의 과목으로 검색하고 선택하세요</p></div>', unsafe_allow_html=True)

# CSV 업로드 대안 제공
uploaded_file = st.file_uploader("CSV 파일 업로드 (선택사항)", type=['csv'], help="Google Sheets에서 다운로드한 CSV 파일을 업로드할 수 있습니다.")

# 데이터 로드
with st.spinner("강사 데이터를 불러오는 중..."):
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()
            st.success(f"CSV 파일을 성공적으로 읽었습니다. ({len(df)}개 행)")
        except Exception as e:
            st.error(f"CSV 파일 읽기 실패: {str(e)}")
            df = pd.DataFrame()
    else:
        df = load_instructor_data()

if df.empty:
    st.error("강사 데이터를 불러올 수 없습니다. 구글 시트 연결을 확인해주세요.")
    
    with st.expander("🔧 문제 해결 방법 보기"):
        st.markdown("""
        ### Google Sheets 접근 권한 설정 필요
        
        **⚠️ 중요: Excel 파일(.xlsx)인 경우**
        - Google Sheets 형식으로 변환 필요
        1. Google Drive에서 파일 열기
        2. "Google 스프레드시트로 열기" 클릭
        3. 파일 > Google 스프레드시트로 저장
        
        **방법 1: 서비스 계정 권한 부여 (권장)**
        1. Google Sheets 파일 열기
        2. "공유" 버튼 클릭
        3. 이메일 추가: `ai-coding@huhsame-project-1.iam.gserviceaccount.com`
        4. 권한: "뷰어" 선택
        5. "전송" 클릭
        
        **방법 2: 공개 시트로 전환**
        1. Google Sheets 파일 열기
        2. "공유" 버튼 클릭
        3. "링크가 있는 모든 사용자" 설정
        4. "랜덤한 링크가 있는 모든 사용자"를 "뷰어"로 변경
        
        **방법 3: CSV로 수동 다운로드**
        1. Google Sheets에서 "파일 > 다운로드 > 쉼표로 구분된 값(.csv)" 선택
        2. CSV 파일을 앱에 업로드하여 사용
        """)
    
    st.stop()

# 관리자용 강사 정보 업로드 섹션
st.markdown("---")
st.markdown("### 🛠️ 관리자 기능")

with st.expander("📤 강사 정보 업로드", expanded=False):
    st.markdown("**Google Sheets에 강사 정보를 추가합니다.**")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["새 강사 추가", "엑셀 일괄 업로드"])
    
    with tab1:
        st.markdown("#### 개별 강사 정보 입력")
        
        with st.form("instructor_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                instr_name = st.text_input("강사 이름 *", key="form_name")
                affiliation = st.text_input("소속 *", key="form_affiliation")
                job = st.text_input("직업", key="form_job")
                subject = st.text_input("강의 과목", key="form_subject")
                email = st.text_input("이메일 주소", key="form_email")
                main_category = st.text_input("대분야", key="form_main_cat")
            
            with col2:
                sub_category = st.text_input("소분야", key="form_sub_cat")
                satisfaction = st.text_input("만족도", key="form_satisfaction")
                feedback = st.text_area("학습자 주요 의견", height=100, key="form_feedback")
                manager_comment = st.text_area("담당자 의견", height=100, key="form_manager")
            
            st.caption("💡 필수 항목(*)만 입력해도 저장 가능합니다.")
            
            submitted = st.form_submit_button("💾 강사 정보 저장", use_container_width=True, type="primary")
            
            if submitted:
                if not instr_name or not affiliation:
                    st.error("강사 이름과 소속은 필수 항목입니다.")
                else:
                    # TODO: 실제로 Google Sheets에 저장하는 로직 구현
                    st.success(f"✅ '{instr_name}' 강사 정보가 저장되었습니다!")
                    st.info("⚠️ 현재는 데모 모드입니다. 실제 저장 기능은 Google Sheets API 설정 후 사용 가능합니다.")
    
    with tab2:
        st.markdown("#### 엑셀/CSV 파일 업로드")
        
        uploaded_batch = st.file_uploader(
            "엑셀(.xlsx) 또는 CSV(.csv) 파일을 선택하세요",
            type=['xlsx', 'xls', 'csv'],
            help="여러 강사 정보가 포함된 파일을 업로드할 수 있습니다."
        )
        
        if uploaded_batch is not None:
            try:
                # 파일 확장자 확인
                file_extension = uploaded_batch.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    batch_df = pd.read_csv(uploaded_batch)
                elif file_extension in ['xlsx', 'xls']:
                    batch_df = pd.read_excel(uploaded_batch)
                else:
                    st.error("지원하지 않는 파일 형식입니다.")
                    batch_df = None
                
                if batch_df is not None and not batch_df.empty:
                    st.success(f"✅ 파일 읽기 성공! {len(batch_df)}개 행을 발견했습니다.")
                    
                    # 데이터 미리보기
                    with st.expander("📋 데이터 미리보기", expanded=True):
                        st.dataframe(batch_df.head(10), use_container_width=True)
                    
                    # 업로드 버튼
                    if st.button("⬆️ 엑셀 데이터 업로드", type="primary", use_container_width=True):
                        # TODO: 실제로 Google Sheets에 저장하는 로직 구현
                        st.success(f"✅ {len(batch_df)}개 강사 정보가 저장되었습니다!")
                        st.info("⚠️ 현재는 데모 모드입니다. 실제 저장 기능은 Google Sheets API 설정 후 사용 가능합니다.")
            
            except Exception as e:
                st.error(f"파일 읽기 실패: {str(e)}")

st.markdown("---")

# 검색 입력 섹션
col1, col2 = st.columns([4, 1])

with col1:
    search_query = st.text_input(
        "검색어를 입력하세요",
        placeholder="예: 김양민, 마케팅, 전략, Management 등",
        key="search_input"
    )

with col2:
    search_type = st.selectbox(
        "검색 범위",
        options=['all', 'name', 'field', 'subject'],
        format_func=lambda x: {
            'all': '전체',
            'name': '강사이름',
            'field': '분야',
            'subject': '강의과목'
        }[x],
        key="search_type"
    )

# 검색 버튼
search_button = st.button("🔍 검색", type="primary", use_container_width=True)

# 검색 실행 및 결과 표시
if search_button and search_query:
    with st.spinner("검색 중..."):
        results = search_instructors(df, search_query, search_type)
        st.session_state.search_results = results
        st.session_state.web_search_result = None  # 초기화
        
        # 검색어와 타입을 세션 상태에 저장 (rerun 후에도 유지)
        st.session_state.last_search_query = search_query
        st.session_state.last_search_type = search_type
        
        # 검색 결과가 없고, 검색 타입이 이름 검색인 경우 네이버 인물검색 시도
        if results.empty and (search_type == 'name' or search_type == 'all'):
            with st.spinner("웹에서 정보를 검색하는 중..."):
                web_result = search_naver_person(search_query)
                if web_result:
                    st.session_state.web_search_result = web_result
    # 새 검색 시 상세 정보 초기화
    st.session_state.selected_instructor = None
    st.session_state.selected_instructor_idx = None

# 검색 결과가 있으면 표시
if not st.session_state.search_results.empty:
    results = st.session_state.search_results
    
    if not results.empty:
        st.markdown(f"### 📋 검색 결과 ({len(results)}명)")
        
        # 검색 결과 리스트
        for idx, instructor in results.iterrows():
            with st.container():
                # 컬럼명 찾기
                name_col = [col for col in instructor.index if '강사' in col and '이름' in col]
                affiliation_col = [col for col in instructor.index if '소속' in col]
                job_col = [col for col in instructor.index if '직업' in col]
                
                name = instructor[name_col[0]] if name_col and pd.notna(instructor[name_col[0]]) else "이름 없음"
                affiliation = instructor[affiliation_col[0]] if affiliation_col and pd.notna(instructor[affiliation_col[0]]) else "소속 정보 없음"
                job = instructor[job_col[0]] if job_col and pd.notna(instructor[job_col[0]]) else "직업 정보 없음"
                
                # 카드 표시
                st.markdown('<div class="instructor-card">', unsafe_allow_html=True)
                
                col_name, col_detail = st.columns([1, 2])
                
                with col_name:
                    st.markdown(f"#### 👤 **{name}**")
                
                with col_detail:
                    st.markdown(f"**🏢 소속:** {affiliation}  |  **💼 직업:** {job}")
                
                # 선택 버튼 (토글 기능)
                button_text = "❌ 상세 정보 닫기" if st.session_state.selected_instructor_idx == idx else "📖 상세 정보 보기"
                if st.button(button_text, key=f"detail_{idx}", use_container_width=True):
                    if st.session_state.selected_instructor_idx == idx:
                        # 이미 선택된 항목이면 닫기
                        st.session_state.selected_instructor = None
                        st.session_state.selected_instructor_idx = None
                    else:
                        # 새로운 항목 선택
                        st.session_state.selected_instructor = instructor.to_dict()
                        st.session_state.selected_instructor_idx = idx
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # 선택된 항목이면 바로 아래에 상세 정보 표시
                if st.session_state.selected_instructor_idx == idx and st.session_state.selected_instructor is not None:
                    st.markdown("---")
                    st.markdown("### 📖 강사 상세 정보")
                    
                    st.markdown('<div class="info-card">', unsafe_allow_html=True)
                    
                    # 강사 이름
                    name_cols = [key for key in st.session_state.selected_instructor.keys() if '강사' in key and '이름' in key]
                    if name_cols:
                        st.markdown(f"#### 👤 **{st.session_state.selected_instructor[name_cols[0]]}**")
                    
                    # 소속
                    affiliation_cols = [key for key in st.session_state.selected_instructor.keys() if '소속' in key]
                    if affiliation_cols and pd.notna(st.session_state.selected_instructor[affiliation_cols[0]]):
                        st.markdown(f"**🏢 소속:** {st.session_state.selected_instructor[affiliation_cols[0]]}")
                    
                    # 직업
                    job_cols = [key for key in st.session_state.selected_instructor.keys() if '직업' in key]
                    if job_cols and pd.notna(st.session_state.selected_instructor[job_cols[0]]):
                        st.markdown(f"**💼 직업:** {st.session_state.selected_instructor[job_cols[0]]}")
                    
                    # 강의 과목
                    subject_cols = [key for key in st.session_state.selected_instructor.keys() if '강의' in key and '과목' in key]
                    if subject_cols and pd.notna(st.session_state.selected_instructor[subject_cols[0]]):
                        st.markdown(f"**📚 강의 과목:** {st.session_state.selected_instructor[subject_cols[0]]}")
                    
                    # 이메일
                    email_cols = [key for key in st.session_state.selected_instructor.keys() if 'e-mail' in key or '이메일' in key]
                    if email_cols and pd.notna(st.session_state.selected_instructor[email_cols[0]]):
                        st.markdown(f"**📧 이메일:** {st.session_state.selected_instructor[email_cols[0]]}")
                    
                    # 대분야
                    main_cat_cols = [key for key in st.session_state.selected_instructor.keys() if '대분야' in key]
                    if main_cat_cols and pd.notna(st.session_state.selected_instructor[main_cat_cols[0]]):
                        st.markdown(f"**🏷️ 대분야:** {st.session_state.selected_instructor[main_cat_cols[0]]}")
                    
                    # 소분야
                    sub_cat_cols = [key for key in st.session_state.selected_instructor.keys() if '소분야' in key]
                    if sub_cat_cols and pd.notna(st.session_state.selected_instructor[sub_cat_cols[0]]):
                        st.markdown(f"**🏷️ 소분야:** {st.session_state.selected_instructor[sub_cat_cols[0]]}")
                    
                    # 만족도
                    satisfaction_cols = [key for key in st.session_state.selected_instructor.keys() if '만족도' in key]
                    if satisfaction_cols and pd.notna(st.session_state.selected_instructor[satisfaction_cols[0]]):
                        st.markdown(f"**⭐ 만족도:** {st.session_state.selected_instructor[satisfaction_cols[0]]}")
                    
                    # 학습자 주요 의견
                    feedback_cols = [key for key in st.session_state.selected_instructor.keys() if '학습자' in key or '의견' in key]
                    if feedback_cols and pd.notna(st.session_state.selected_instructor[feedback_cols[0]]):
                        st.markdown("**💬 학습자 주요 의견:**")
                        st.markdown(f"{st.session_state.selected_instructor[feedback_cols[0]]}")
                    
                    # 담당자 의견
                    manager_cols = [key for key in st.session_state.selected_instructor.keys() if '담당자' in key]
                    if manager_cols and pd.notna(st.session_state.selected_instructor[manager_cols[0]]):
                        st.markdown("**📝 담당자 의견:**")
                        st.markdown(f"{st.session_state.selected_instructor[manager_cols[0]]}")
                    
                    # 유튜브 링크 검색 및 표시
                    instructor_name = None
                    instructor_job = None
                    instructor_main_field = None
                    instructor_sub_field = None
                    
                    if name_cols:
                        instructor_name = st.session_state.selected_instructor[name_cols[0]]
                    
                    # 직업 정보 추출
                    if job_cols and pd.notna(st.session_state.selected_instructor.get(job_cols[0])):
                        instructor_job = st.session_state.selected_instructor[job_cols[0]]
                    
                    # 대분야 정보 추출
                    if main_cat_cols and pd.notna(st.session_state.selected_instructor.get(main_cat_cols[0])):
                        instructor_main_field = st.session_state.selected_instructor[main_cat_cols[0]]
                    
                    # 소분야 정보 추출
                    if sub_cat_cols and pd.notna(st.session_state.selected_instructor.get(sub_cat_cols[0])):
                        instructor_sub_field = st.session_state.selected_instructor[sub_cat_cols[0]]
                    
                    if instructor_name and pd.notna(instructor_name):
                        # 유튜브 링크 리스트를 세션 상태에 캐시 (추가 정보 포함하여 고유 키 생성)
                        cache_key_parts = [instructor_name]
                        if instructor_job:
                            cache_key_parts.append(str(instructor_job))
                        if instructor_sub_field:
                            cache_key_parts.append(str(instructor_sub_field))
                        elif instructor_main_field:
                            cache_key_parts.append(str(instructor_main_field))
                        
                        youtube_cache_key = f"youtube_links_{'_'.join(cache_key_parts)}"
                        
                        if youtube_cache_key not in st.session_state:
                            with st.spinner("유튜브 채널/동영상 검색 중..."):
                                youtube_links = search_youtube_channel(
                                    instructor_name, 
                                    job=instructor_job,
                                    main_field=instructor_main_field,
                                    sub_field=instructor_sub_field
                                )
                                st.session_state[youtube_cache_key] = youtube_links
                        else:
                            youtube_links = st.session_state[youtube_cache_key]
                        
                        if youtube_links:
                            # 유튜브 리스트 및 요약 정보 표시
                            display_youtube_list_and_summary(youtube_links, instructor_name, instructor_name)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("---")

# 웹 검색 결과가 있으면 표시 (rerun 후에도 유지)
if st.session_state.web_search_result:
    # 검색어 가져오기
    search_query_for_display = st.session_state.get('last_search_query', search_query)
    
    st.warning(f"'{search_query_for_display}'에 대한 검색 결과가 없습니다.")
    
    if True:  # 항상 웹 검색 결과 표시
        st.markdown("---")
        st.markdown("### 🌐 네이버 인물검색 결과")
        
        web_result = st.session_state.web_search_result
        st.markdown('<div class="info-card" style="border-left-color: #03c75a;">', unsafe_allow_html=True)
        
        # 제목
        st.markdown(f"#### 👤 **{web_result.get('name', search_query)}**")
        st.caption(f"출처: {web_result.get('source', '네이버 인물검색')}")
        
        # 정보 표시
        if web_result.get('info'):
            info = web_result['info']
            
            # 이미지가 있으면 표시
            if '이미지' in info and info['이미지']:
                st.image(info['이미지'], width=150)
            
            # 이름
            if '이름' in info:
                st.markdown(f"**이름:** {info['이름']}")
            
            # 기본 정보 (생년월일, 직업, 소속 등)
            for key, value in info.items():
                if key not in ['이름', '이미지', '설명', '약력', '유튜브'] and value:
                    st.markdown(f"**{key}:** {value}")
            
            # 설명
            if '설명' in info and info['설명']:
                st.markdown("---")
                st.markdown("**📝 설명:**")
                st.markdown(info['설명'])
            
            # 약력
            if '약력' in info and info['약력']:
                st.markdown("---")
                st.markdown("**📚 약력:**")
                st.markdown(info['약력'])
            
            # 유튜브 링크 검색 및 표시 (네이버 검색 결과와 관계없이 유튜브에서 직접 검색)
            person_name = web_result.get('name', search_query)
            if person_name:
                st.markdown("---")
                # 유튜브 링크 리스트를 세션 상태에 캐시
                youtube_cache_key = f"youtube_links_naver_{person_name}"
                if youtube_cache_key not in st.session_state:
                    with st.spinner("유튜브 채널/동영상 검색 중..."):
                        youtube_links = search_youtube_channel(person_name)
                        st.session_state[youtube_cache_key] = youtube_links
                else:
                    youtube_links = st.session_state[youtube_cache_key]
                
                if youtube_links:
                    # 유튜브 리스트 및 요약 정보 표시
                    display_youtube_list_and_summary(youtube_links, person_name, f"naver_{person_name}")
        
        # 네이버 검색 링크
        if web_result.get('url'):
            st.markdown("---")
            st.markdown(f"[🔗 네이버 인물검색에서 더 보기]({web_result['url']})")
        
        st.markdown('</div>', unsafe_allow_html=True)

# 검색 버튼이 눌렸지만 결과가 없고 웹 검색 결과도 없는 경우
elif search_button and search_query and st.session_state.search_results.empty and not st.session_state.web_search_result:
    st.warning(f"'{search_query}'에 대한 검색 결과가 없습니다.")
    st.info("💡 **팁:** 검색어를 변경하거나 '전체' 검색 범위를 사용해보세요.")
    st.info("💡 **팁:** 강사 이름으로 검색하면 네이버 인물검색에서 정보를 찾을 수 있습니다.")
    
    # 유튜브에서 검색 제공
    st.markdown("---")
    st.markdown(f"### 📺 '{search_query}' 유튜브 검색 결과")
    
    # 유튜브 링크 리스트를 세션 상태에 캐시
    youtube_cache_key = f"youtube_links_direct_{search_query}"
    if youtube_cache_key not in st.session_state:
        with st.spinner("유튜브 채널/동영상 검색 중..."):
            youtube_links = search_youtube_channel(search_query)
            st.session_state[youtube_cache_key] = youtube_links
    else:
        youtube_links = st.session_state[youtube_cache_key]
    
    if youtube_links:
        # 유튜브 리스트 및 요약 정보 표시
        display_youtube_list_and_summary(youtube_links, search_query, f"direct_{search_query}")

# 사이드바에 통계 표시
with st.sidebar:
    st.markdown("### 📊 통계")
    
    # 중복 제거된 강사 수 계산 (이름 + 이메일이 같으면 동일인물)
    if not df.empty:
        # 컬럼명 찾기
        name_cols = [col for col in df.columns if '강사' in col and '이름' in col]
        email_cols = [col for col in df.columns if 'e-mail' in col.lower() or '이메일' in col]
        subfield_cols = [col for col in df.columns if '소분야' in col]
        
        # 중복 제거된 강사 수 (이름 + 이메일 기준)
        if name_cols and email_cols:
            name_col = name_cols[0]
            email_col = email_cols[0]
            # 이름과 이메일이 모두 있는 데이터만 필터링하여 중복 제거
            df_with_info = df[df[name_col].notna() & df[email_col].notna()]
            unique_count = df_with_info.drop_duplicates(subset=[name_col, email_col]).shape[0]
            
            st.metric("총 강사 수", unique_count)
        else:
            # 이름이나 이메일 컬럼이 없으면 전체 행 수 표시
            st.metric("총 강사 수", len(df))
        
        # 소분야별 강사 수 표시
        if subfield_cols:
            st.markdown("---")
            st.markdown("### 📈 소분야별 통계")
            
            subfield_col = subfield_cols[0]
            
            # 중복 제거된 데이터로 소분야별 집계
            if name_cols and email_cols:
                df_unique = df_with_info.drop_duplicates(subset=[name_col, email_col])
            else:
                df_unique = df.copy()
            
            # 소분야별 카운트
            subfield_counts = df_unique[subfield_col].value_counts()
            
            # 상위 10개만 표시
            top_subfields = subfield_counts.head(10)
            
            if not top_subfields.empty:
                # 지표로 표시
                st.markdown("**Top 5 소분야:**")
                for idx, (subfield, count) in enumerate(top_subfields.head(5).items(), 1):
                    if pd.notna(subfield) and subfield != '':
                        st.markdown(f"{idx}. **{subfield}**: {count}명")
                
                # 그래프 표시
                st.markdown("---")
                st.markdown("**전체 소분야 분포:**")
                
                # Streamlit 내장 bar_chart 사용
                st.bar_chart(top_subfields)
                
                # 상세 정보
                with st.expander("📊 전체 소분야 보기"):
                    for subfield, count in subfield_counts.items():
                        if pd.notna(subfield) and subfield != '':
                            st.markdown(f"• {subfield}: {count}명")
    else:
        st.metric("총 강사 수", 0)
    
    # 검색 기록 표시
    if search_query and search_button:
        results = search_instructors(df, search_query, search_type)
        if not results.empty:
            st.markdown("---")
            st.metric("검색 결과", len(results))

# 푸터
st.markdown("---")
st.caption("💡 한 가지 검색어만 입력해도 강사 이름, 소속, 직업이 표시되며, 클릭하면 상세 정보를 볼 수 있습니다.")


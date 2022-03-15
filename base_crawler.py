
from enum import Enum
import json
import logging
import os
import re
import textstat
from dataclasses import InitVar, asdict, dataclass, field
from typing import Any, Dict, List, Optional

import requests
import webvtt
import youtube_dl
from lxml import html

import multiprocessing

import subprocess
import re
# from tqdm.notebook import tqdm


# Xpath constants
video_url_Xpath = ".//div/div[1]"

# Youtube constants
YOUTUBE_PATH = "youtube"
BASE_YOUTUBE_URL = "https://www.youtube.com/watch?v={}"

# YoutubeDL constants
ydl_opts = {
    # 'outtmpl': f'{YOUTUBE_PATH}/%(title)s_%(ext)s.mp4',
    'outtmpl': f'{YOUTUBE_PATH}/%(id)s',
    'writesubtitles': True,
    'quiet': True,
    'no_warnings': True,
    # 'subtitle': '--write-sub --write-auto-sub  --sub-lang en',
    'skip_download': True  # Change to False to enable donwload
}

###############################################################################
########################     FUNCTIONS FOR LOGING       #######################
###############################################################################




def get_csrfToken(TOKEN_URL):
    """
    Get CSRF tokens from body and cookies response
    """
    logging.info('Getting initial CSRF token.')
    try:
        response = requests.request("GET", TOKEN_URL)
        response_json = json.loads(response.text)
        return response_json["csrfToken"], response.cookies["csrftoken"]
    except:
        logging.warning('Did not find the CSRF token.')
        raise ConnectionError('Did not find the CSRF token.')


def get_csrfToken_edge(TOKEN_URL):
    """
    Get CSRF tokens from body and cookies response
    """
    logging.info('Getting initial CSRF token.')
    try:
        response = requests.request("GET", TOKEN_URL)
        return response.cookies["lms_sessionid"], response.cookies["csrftoken"]
    except:
        logging.warning('Did not find the CSRF token.')
        raise ConnectionError('Did not find the CSRF token.')


def edx_get_login_headers(REFER_URL, TOKEN_URL):
    """
    Build the Open edX headers to create future requests.
    """
    logging.info('Building initial headers for future requests.')
    csrfToken, csrftoken = get_csrfToken(TOKEN_URL)
    headers = {
        'User-Agent': 'edX-downloader/0.01',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
        'Referer': REFER_URL,
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken,
        'Cookie': 'csrftoken=' + csrftoken,
    }
    logging.debug('Headers built: %s', headers)
    return headers


def edx_get_login_headers_edge(REFER_URL, TOKEN_URL):
    """
    Build the Open edX headers to create future requests.
    """
    logging.info('Building initial headers for future requests.')
    lms_sessionid, csrftoken = get_csrfToken_edge(TOKEN_URL)
    headers = {
        "Accept": "*/*",
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
        'Referer': REFER_URL,
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrftoken,
        "Origin": "https://edge.edx.org",
        'Cookie': 'experiments_is_enterprise=false; ' + 'csrftoken=' + csrftoken + "; lms_sessionid=" + lms_sessionid,
    }
    logging.debug('Headers built: %s', headers)
    return headers


def edx_login(url, headers, username, password):
    """
    Log in user into the openedx website.
    """
    logging.info('Logging into Open edX site: %s', url)

    payload = f"email_or_username={username}&password={password}"

    response = requests.request("POST", url, data=payload, headers=headers)

    resp = json.loads(response.text)
    lms_sessionid = response.cookies["lms_sessionid"]
    user_info_cookie = response.cookies["prod-edx-user-info"]
    pattern = "username: (.*?)\\\\054"
    username = re.search(pattern, user_info_cookie).group(1)
    return resp, lms_sessionid, username


def edx_login_edge(url, headers, username, password):
    """
    Log in user into the openedx website.
    """
    logging.info('Logging into Open edX site: %s', url)

    payload = f"email={username}&password={password}"

    response = requests.request("POST", url, data=payload, headers=headers)

    resp = json.loads(response.text)
    lms_sessionid = response.cookies["lms_sessionid"]
    csrftoken = response.cookies["csrftoken"]
    user_info_cookie = response.cookies["edge-edx-user-info"]
    pattern = "username: (.*?)\\\\054"
    username = re.search(pattern, user_info_cookie).group(1)

    return resp, lms_sessionid, csrftoken, username


def edx_get_loged_headers(lms_sessionid, REFER_URL):
    """
    Build the Open edX headers after logged to create future requests.
    """
    logging.info('Building initial headers for future requests.')
    headers = {
        'User-Agent': 'edX-downloader/0.01',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': REFER_URL,
        'Cookie': 'lms_sessionid=' + lms_sessionid,
    }
    logging.debug('Headers built: %s', headers)
    return headers


def edx_get_loged_headers_edge(lms_sessionid, csrftoken, REFER_URL):
    """
    Build the Open edX headers after logged to create future requests.
    """
    logging.info('Building initial headers for future requests.')
    headers = {
        'User-Agent': 'edX-downloader/0.01',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': REFER_URL,
        'Cookie': 'csrftoken=' + csrftoken + ';lms_sessionid=' + lms_sessionid,
    }
    logging.debug('Headers built: %s', headers)
    return headers

def get_courses_by_url(user_email, password,IS_EDGE=False):
    if IS_EDGE:

        BASE_URL = 'https://edge.edx.org'

        BASE_OUTLINE_URL = BASE_URL + '/api/course_home/outline'
        BASE_BLOCK_URL = BASE_URL + '/api/courses/v2/blocks/'

        REFER_URL =  BASE_URL + '/login'
        TOKEN_URL = BASE_URL + '/login'
        EDX_HOMEPAGE = BASE_URL + '/user_api/v2/account/login_session'
        LOGIN_API = BASE_URL + '/api/user/v1/account/login_session/'

        DASHBOARD = BASE_URL + '/dashboard'
    else:
        
        BASE_URL = 'https://courses.edx.org'

        BASE_OUTLINE_URL = BASE_URL + '/api/course_home/outline'
        BASE_BLOCK_URL = BASE_URL + '/api/courses/v2/blocks/'

        REFER_URL = 'https://authn.edx.org'
        TOKEN_URL = BASE_URL + '/csrf/api/v1/token'
        EDX_HOMEPAGE = BASE_URL + '/user_api/v2/account/login_session'
        LOGIN_API = BASE_URL + '/api/user/v2/account/login_session/'
        DASHBOARD = BASE_URL + '/dashboard'

    if IS_EDGE:
        login_headers = edx_get_login_headers_edge(REFER_URL, TOKEN_URL)
        resp, lms_sessionid, csrftoken, username = edx_login_edge(LOGIN_API, login_headers, user_email, password) 
        if not resp.get('success', False):
            logging.error(resp.get('value', "Wrong Email or Password."))
            exit(ExitCode.WRONG_EMAIL_OR_PASSWORD)
        headers = edx_get_loged_headers_edge(lms_sessionid, csrftoken, REFER_URL)
        courses = get_courses_info(headers)
    else:
        login_headers = edx_get_login_headers(REFER_URL, TOKEN_URL)
        resp, lms_sessionid, username = edx_login(LOGIN_API, login_headers, user_email, password) 
        if not resp.get('success', False):
            logging.error(resp.get('value', "Wrong Email or Password."))
            exit(ExitCode.WRONG_EMAIL_OR_PASSWORD)
        headers = edx_get_loged_headers(lms_sessionid, REFER_URL)
        courses = get_courses_info(headers, DASHBOARD)

    return courses, headers, username, BASE_BLOCK_URL

def get_courses_info(headers, DASHBOARD):
    """
    Extracts the courses information from the dashboard.
    """
    logging.info('Extracting course information from dashboard.')
    courses_Xpath = "/html/body/div[2]/div[2]/section[1]/main/section/ul/li"

    name_Xpath = ".//div/article/section/div[2]/h3/a"
    started_Xpath = ".//div/article/section/div[2]/div/div[1]/div[1]/span[3]/span"
    continue_Xpath = ".//div/article/section/div[2]/div/div[2]/a"

    response = requests.request("GET", DASHBOARD, headers=headers)
    with open("dashboard.html", "w") as f:
        f.write(response.text)

    tree = html.fromstring(response.text)
    courses_ref = tree.xpath(courses_Xpath)
    courses = []
    for ref in courses_ref:
        # Get name and link
        name_ref = ref.xpath(name_Xpath)[0]
        # Check if its archived
        continue_ref = ref.xpath(continue_Xpath)[0]
        continue_text = continue_ref.text
        is_archived = "archived" in continue_text.lower()
        # Check started status 🚨
        started_ref = ref.xpath(started_Xpath)[0]
        started_text = started_ref.attrib.get("data-string")
        # Create Course object 🚀
        course_id = name_ref.attrib.get("data-course-key")
        course_url = name_ref.attrib.get('href')
        course_name = name_ref.text
        is_started = started_text.startswith(
            "Started")  # TODO: Dont know if its enough
        courses.append(Course(id=course_id, url=course_url,
                       name=course_name, started=is_started, is_archived=is_archived))

    logging.debug('Data extracted: %s', courses)

    return courses
###############################################################################
########################  END OF FUNCTIONS FOR LOGING   #######################
###############################################################################


###############################################################################
#####################   DATA CLASSES OF COMMON RESPONSES   ####################
###############################################################################

@dataclass
class Quiz:
    id: str = ""
    section: str = ""
    subsection: str = ""
    unit: str = ""
    body: str = ""


@dataclass
class Text:
    id: str = ""
    section: str = ""
    subsection: str = ""
    unit: str = ""
    body: str = ""


@dataclass
class Video:
    id: str = ""
    section: str = ""
    subsection: str = ""
    unit: str = ""
    video_sources: str = ""
    video_duration: int = 0
    video_sources: List[str] = field(default_factory=list)
    speech_period: List[float] = field(default_factory=list)
    transcript_en: List[str] = field(default_factory=list)
    is_youtube: bool = False


@dataclass
class Unit:
    videos: List[Video] = field(default_factory=list)
    resources_urls: List[str] = field(default_factory=list)


@dataclass
class Subsection:
    position: int
    url: str
    name: str
    units: List[Unit] = field(default_factory=list)


@dataclass
class Section:
    position: int
    url: str
    name: str
    subsections: List[Subsection] = field(default_factory=list)


@dataclass
class Course:
    id: str
    url: str
    name: str
    started: bool
    is_archived: bool
    sections: List[Section] = field(default_factory=list)


@dataclass
class CourseBlock:
    id: str
    block_id: str
    lms_web_url: str
    legacy_web_url: str
    student_view_url: str
    type: str
    display_name: str
    graded: bool
    children: List[str] = field(default_factory=list)
    effort_time: int = 0
    effort_activities: int = 0
    has_scheduled_content: bool = False


@dataclass
class ChapterBlock:
    id: str
    block_id: str
    lms_web_url: str
    legacy_web_url: str
    student_view_url: str
    type: str
    display_name: str
    graded: bool
    children: List[str] = field(default_factory=list)
    effort_time: int = 0
    effort_activities: int = 0


@dataclass
class SequenceBlock:
    id: str
    block_id: str
    lms_web_url: str
    legacy_web_url: str
    student_view_url: str
    type: str
    display_name: str
    graded: bool
    effort_time: int = 0
    children: List[str] = field(default_factory=list)
    effort_activities: int = 0
    special_exam_info: object = None


@dataclass
class VerticalBlock:
    id: str
    block_id: str
    lms_web_url: str
    legacy_web_url: str
    student_view_url: str
    type: str
    display_name: str
    graded: bool
    effort_time: int = 0
    effort_activities: int = 0


@dataclass
class EdgeBlock:
    complete: bool
    description: any
    display_name: str
    due: any
    effort_activities: any
    effort_time: any
    icon: any
    id: str
    lms_web_url: str
    legacy_web_url: str
    resume_block: bool
    type: str
    has_scheduled_content: any
    children: List[str] = field(default_factory=list)
###############################################################################
########################       END OF OBJECTS           #######################
###############################################################################


###############################################################################
########################    DOWNLOAD HTML FROM UNIT     #######################
###############################################################################

def dowloadVerticalHTML(course_id, vertical_id, url, headers):
    """
    Fetch the html from specific unit.
    """
    querystring = {"show_title": "0", "show_bookmark_button": "0",
                   "recheck_access": "1", "view": "student_view"}
    vertical_response = requests.request(
        "GET", url, headers=headers, params=querystring)
    # STORE FILE AT CORRESPONDING LOCATION
    with open(f"courses/{course_id}/htmls/{vertical_id}.html", 'w') as f:
        f.write(vertical_response.text)


def getYoutubeCaptions(youtube_id):
    """
    Get the captions from youtube if possible.
    """
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        dictMeta = ydl.extract_info(
            BASE_YOUTUBE_URL.format(youtube_id),
            download=True)
    duration = dictMeta["duration"]
    if not "subtitles" in dictMeta or not len(dictMeta["subtitles"]):
        return [], [], duration
    for file in os.listdir(YOUTUBE_PATH):
        if file.startswith(youtube_id) and file.endswith(".vtt"):
            vtt = webvtt.read(f'./{YOUTUBE_PATH}/{file}')
            lines = [line.text for line in vtt]
            speech_period = [
                round(line.end_in_seconds - line.start_in_seconds, 2) for line in vtt]
            break
    return lines, speech_period, duration


def getVideoDuration(video_sources):
    """
    Get duration of video from url, since duration not found in html body
    """
    r = re.compile(".*mp4")
    mp4_list = list(filter(r.match, video_sources))  # Read Note below
    url = mp4_list[0] if mp4_list else video_sources[0]
    # if not mp4_list:
    #     print("🚨 No mp4 source was found")
    # url = mp4_list[0]

    cmnd = ['ffprobe', '-i', url, '-show_entries',
            'format=duration', '-v', 'quiet', '-of', 'csv=p=0']
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if err:
        print("========= error ========")
        print(err)
    # print("🚀 Video duration found from", url, out)
    return float(out)


def getVideoObject(section, subsection, unit, vertical_ref):
    """
    Get video block from vertical html, then extracts the details subtitles, duration, sources, etc.
    """
    # Locate video block in vertical html
    url_video = vertical_ref.xpath(video_url_Xpath)[0]
    url_video_json = json.loads(url_video.attrib.get("data-metadata"))
    video_id = url_video.attrib.get("id")
    data_id = vertical_ref.attrib.get("data-id")
    is_youtube = not url_video_json["sources"]

    if is_youtube:
        youtube_id = url_video_json["streams"].split(":")[-1]
        try:
            transcript, speech_period, video_duration = getYoutubeCaptions(
                youtube_id)
            video_obj = Video(id=data_id,
                              section=section,
                              subsection=subsection,
                              unit=unit,
                              video_sources=[youtube_id],
                              transcript_en=transcript,
                              video_duration=video_duration,
                              speech_period=speech_period,
                              is_youtube=True)
            return video_obj
        except:
            return

    else:
        # If it is not youtube, then it is a embedded video
        video_sources = url_video_json["sources"]

        # Get the video transcript
        video_transcript_url = url_video_json["lmsRootURL"] + url_video_json["transcriptTranslationUrl"].replace(
            "__lang__", url_video_json["transcriptLanguage"])

        video_duration = url_video_json["duration"]

        video_duration = video_duration if video_duration else getVideoDuration(
            video_sources)

        transcript_response = requests.request("GET", video_transcript_url)

        # There is not available transcript
        if not transcript_response.ok:
            video_obj = Video(id=data_id,
                              section=section,
                              subsection=subsection,
                              unit=unit,
                              video_sources=video_sources,
                              video_duration=int(video_duration))
        else:
            transcript_json = json.loads(transcript_response.text)
            transcript_en = transcript_json["text"]

            # Calculate the speech period in seconds
            speech_period = [
                (y-x)/1000 for x, y in zip(transcript_json["start"], transcript_json["end"])]
            video_obj = Video(id=data_id,
                              section=section,
                              subsection=subsection,
                              unit=unit,
                              video_sources=video_sources,
                              transcript_en=transcript_en,
                              video_duration=int(video_duration),
                              speech_period=speech_period)

        return video_obj


def getTextObj(section, subsection, unit, vertical_ref):
    """
    Get text block from vertical html, then extracts the readable text.
    """
    # Remove the text from unreadable html
    for squit_ref in vertical_ref.xpath(".//*/style | .//*[@class='wrap-instructor-info'] | //*[@aria-hidden='true'] | //*/button | //*/script | //*[contains(@class, 'sr')] | //*[@class='action'] | //*[@class='notification-message']"):
        squit_ref.getparent().remove(squit_ref)

    html_text = " ".join(
        [text for text in vertical_ref.itertext() if text.strip()])

    data_id = vertical_ref.attrib.get("data-id")

    text_obj = Text(id=data_id,
                    section=section,
                    subsection=subsection,
                    unit=unit,
                    body=html_text)
    return text_obj


def getQuizObj(section, subsection, unit, vertical_ref):
    """
    Get quiz block from vertical html, then extracts the details of the quiz.
    """
    # Locate quiz block in vertical html
    quiz_refs = vertical_ref.xpath(".//*[@class='problems-wrapper']")
    if not quiz_refs:
        return
    # Get real html from quiz, since it is store inside the attribute called data-metadata
    quiz_tree = html.fromstring(quiz_refs[0].attrib.get("data-content"))

    # Remove unnecessary html from quiz
    for squit_ref in quiz_tree.xpath("//*[aria-hidden='true'] | //*/button | //*/script | //*[@class='sr'] | //*[@class='action'] | //*[@class='notification-message']"):
        squit_ref.getparent().remove(squit_ref)

    html_text = " ".join(
        [text for text in quiz_tree.itertext() if text.strip()])

    data_id = vertical_ref.attrib.get("data-id")

    quiz_obj = Quiz(id=data_id,
                    section=section,
                    subsection=subsection,
                    unit=unit,
                    body=html_text)

    return quiz_obj


def getVerticalRefObj(section, subsection, unit, vertical_ref):
    """
    Get vertical block from vertical html. It can be video, text or quiz.
    """
    if not vertical_ref.attrib.has_key("data-id"):
        return
    vertical_id = vertical_ref.attrib.get("data-id")
    if "type@video" in vertical_id:
        return getVideoObject(section, subsection, unit, vertical_ref)
    elif "type@html" in vertical_id:
        return getTextObj(section, subsection, unit, vertical_ref)

    elif "type@problem" in vertical_id:
        return getQuizObj(section, subsection, unit, vertical_ref)
    else:
        # TODO: Add other types of verticals
        return


# Body to request course json
def getQueryString(course_id, username):
    return {"course_id": course_id, "username": username, "depth": "3", "requested_fields": "children,effort_activities,effort_time,show_gated_sections,graded,special_exam_info,has_scheduled_content"}


def getCourseStructure(courses, username, headers, BASE_BLOCK_URL):
    """
    Get the course structure for each course.
    """

    for course in courses:
        querystring = getQueryString(course.id, username)

        # Create folder to store the course files
        if not os.path.exists(f"courses/{course.id}"):
            os.makedirs(f"courses/{course.id}/htmls")

        # Fetch course json from edx
        course_response = requests.request(
            "GET", BASE_BLOCK_URL, headers=headers, params=querystring)
        course_response_json = json.loads(course_response.text)

        # Get the course blocks and store keys in a list
        blocks_json = course_response_json["blocks"]
        blocks_keys = [block for block in blocks_json]

        # Last block is the one that contains the course chapters
        course_block = blocks_json[blocks_keys.pop()]

        courseBlock = CourseBlock(**course_block)

        course_childrens = courseBlock.children

        course_structure = dict()
        async_results = []

        # Open a pool of processes to fetch the course chapters faster
        with multiprocessing.Pool(processes=20) as pool:
            # Iterates over the course chapters
            for chapter_i, course_children in enumerate(course_childrens):
                chapterBlock = ChapterBlock(**blocks_json[course_children])
                chapter_id = chapterBlock.id.split("@")[-1]
                course_structure[f"{chapter_id}"] = {}
                # Iterates over each section in the chapter
                for sequence_i, chapter_children in enumerate(chapterBlock.children):
                    sequenceBlock = SequenceBlock(
                        **blocks_json[chapter_children])
                    sequence_id = sequenceBlock.id.split("@")[-1]
                    course_structure[f"{chapter_id}"][f"{sequence_id}"] = {}
                    # Iterates over each unit in the section
                    for vertical_i, sequence_children in enumerate(sequenceBlock.children):
                        verticalBlock = VerticalBlock(
                            **blocks_json[sequence_children])
                        vertical_id = verticalBlock.id.split("@")[-1]
                        course_structure[f"{chapter_id}"][f"{sequence_id}"][f"{vertical_id}"] = {
                            "section": chapterBlock.display_name,
                            "subsection": sequenceBlock.display_name,
                            "unit": verticalBlock.display_name
                        }
                        # Fetch the vertical(unit) html
                        async_result = pool.apply_async(
                            func=dowloadVerticalHTML, args=(course.id, vertical_id, verticalBlock.student_view_url, headers,))
                        async_results.append(async_result)

            # wait for async process to finish
            for result in async_results:
                result.get()
        # Save structure json to file
        with open(f"courses/{course.id}/structure.json", 'w') as f:
            json.dump(course_structure, f)


def getCourseVTQ(course_id):
    """
    Extract the video, text and quiz from the unit html .
    """
    with open(f"courses/{course_id}/structure.json", "r") as f:
        course_structure = json.load(f)

    # Init videos, text and quiz dicts to store the unit videos, text and quiz

    videos = dict()
    texts = dict()
    quizes = dict()

    video_i = 1
    text_i = 1
    quiz_i = 1

    # total = 0
    # for chapter_structure in course_structure:
    #     for sequence_structure in course_structure[chapter_structure]:
    #         for vertical_structure in course_structure[chapter_structure][sequence_structure]:
    #             total += 1

    # with tqdm(total=total,  position=position) as pbar:

    for chapter_structure in course_structure:
        for sequence_structure in course_structure[chapter_structure]:
            for vertical_structure in course_structure[chapter_structure][sequence_structure]:
                unit_json = course_structure[chapter_structure][sequence_structure][vertical_structure]

                # Read unit html
                with open(f"courses/{course_id}/htmls/{vertical_structure}.html", 'r') as f:
                    vertical_html = f.read()

                tree = html.fromstring(vertical_html)

                # Get vertical blocks
                vertical_refs = tree.xpath(
                    "//*[contains(@class,'vert vert-')]")

                for vertical_ref in vertical_refs:
                    # pbar.set_description(f"🔖{unit_json['unit']}", refresh=True)

                    # Get vertical block object
                    if not vertical_ref.attrib.has_key("data-id"):
                        continue

                    vertical_id = vertical_ref.attrib.get("data-id")
                    vertical_obj = getVerticalRefObj(section=unit_json["section"],
                                                     subsection=unit_json["subsection"],
                                                     unit=unit_json["unit"],
                                                     vertical_ref=vertical_ref)

                    if type(vertical_obj) is Video:
                        videos[f"video_{str(video_i).zfill(3)}"] = asdict(
                            vertical_obj)
                        video_i += 1
                    if type(vertical_obj) is Text:
                        texts[f"text_{str(text_i).zfill(3)}"] = asdict(
                            vertical_obj)
                        text_i += 1
                    if type(vertical_obj) is Quiz:
                        quizes[f"quiz_{str(quiz_i).zfill(3)}"] = asdict(
                            vertical_obj)
                        quiz_i += 1

            # pbar.update(1)

    # Store videos, text and quiz to json files
    with open(f"courses/{course_id}/videos.json", 'w') as f:
        json.dump(videos, f)
    with open(f"courses/{course_id}/texts.json", 'w') as f:
        json.dump(texts, f)
    with open(f"courses/{course_id}/quizes.json", 'w') as f:
        json.dump(quizes, f)


def getCourseStats(course_id):
    """
    Generate the course stats from the videos, text and quizes.
    """

    ###### Analysis for japanese is not ready######
    regex = u'[\u2E80-\u9FFF]'
    p = re.compile(regex, re.U)

    name_video = f"courses/{course_id}/videos.json"
    name_text = f"courses/{course_id}/texts.json"
    name_quiz = f"courses/{course_id}/quizes.json"

    with open(name_video, "r") as f:
        video_data = json.load(f)
    with open(name_text, "r") as f:
        text_data = json.load(f)
    with open(name_quiz, "r") as f:
        quiz_data = json.load(f)

    mins = sum([video_data[key]["video_duration"]
               for key in video_data.keys()])
    non_subs = len([key for key in video_data.keys()
                   if not video_data[key]["transcript_en"]])
    total_videos = len(video_data.keys())
    videos_min = mins/60

    body_video = " ".join([" ".join(filter(None, video_data[key]["transcript_en"]))
                          for key in video_data.keys()])
    transcript_en = [word for word in body_video.split()
                     if not p.findall(word)]
    transcript_jp = [word for word in body_video.split() if p.findall(word)]

    len_transcript_en = len(transcript_en)
    len_transcript_jp = len(transcript_jp)

    body_text = " ".join([text_data[key]["body"] for key in text_data.keys()])
    text_en = [word for word in body_text.split() if not p.findall(word)]
    text_jp = [word for word in body_text.split() if p.findall(word)]
    len_text_en = len(text_en)
    len_text_jp = len(text_jp)

    body_quiz = " ".join([quiz_data[key]["body"] for key in quiz_data.keys()])
    quiz_en = [word for word in body_quiz.split() if not p.findall(word)]
    quiz_jp = [word for word in body_quiz.split() if p.findall(word)]
    len_quiz_en = len(quiz_en)
    len_quiz_jp = len(quiz_jp)

    ##########################   REDABILITY   ##########################
    text_redability = TextRedability(body_text)
    video_redability = TextRedability(body_video)
    quiz_redability = TextRedability(body_quiz)

    ########################## END REDABILITY ##########################

    with open(f"courses/{course_id}/stats.json", "w") as f:
        json.dump({
            "videos_min": videos_min,
            "non_subs": non_subs,
            "total_videos": total_videos,
            "len_transcript_en": len_transcript_en,
            "len_transcript_jp": len_transcript_jp,
            "len_text_en": len_text_en,
            "len_text_jp": len_text_jp,
            "len_quiz_en": len_quiz_en,
            "len_quiz_jp": len_quiz_jp,
            "text_redability": asdict(text_redability),
            "video_redability": asdict(video_redability),
            "quiz_redability": asdict(quiz_redability),
        }, f)

##############################################################
######################### REDABILITY #########################
##############################################################

@dataclass
class TextRedability:
    text_data: InitVar[str]
    flesch_reading_ease: float = field(init=False)
    flesch_kincaid_grade: float = field(init=False)
    smog_index: float = field(init=False)
    coleman_liau_index: float = field(init=False)
    automated_readability_index: float = field(init=False)
    dale_chall_readability_score: float = field(init=False)
    difficult_words: float = field(init=False)
    linsear_write_formula: float = field(init=False)
    gunning_fog: float = field(init=False)
    text_standard: str = field(init=False)
    fernandez_huerta: float = field(init=False)
    szigriszt_pazos: float = field(init=False)
    gutierrez_polini: float = field(init=False)
    crawford: float = field(init=False)
    gulpease_index: float = field(init=False)
    osman: float = field(init=False)

    def __post_init__(self, text_data):
        self.flesch_reading_ease = textstat.flesch_reading_ease(text_data)
        self.flesch_kincaid_grade = textstat.flesch_kincaid_grade(text_data)
        self.smog_index = textstat.smog_index(text_data)
        self.coleman_liau_index = textstat.coleman_liau_index(text_data)
        self.automated_readability_index = textstat.automated_readability_index(
            text_data)
        self.dale_chall_readability_score = textstat.dale_chall_readability_score(
            text_data)
        self.difficult_words = textstat.difficult_words(text_data)
        self.linsear_write_formula = textstat.linsear_write_formula(text_data)
        self.gunning_fog = textstat.gunning_fog(text_data)
        self.text_standard = textstat.text_standard(text_data)
        self.fernandez_huerta = textstat.fernandez_huerta(text_data)
        self.szigriszt_pazos = textstat.szigriszt_pazos(text_data)
        self.gutierrez_polini = textstat.gutierrez_polini(text_data)
        self.crawford = textstat.crawford(text_data)
        self.gulpease_index = textstat.gulpease_index(text_data)
        self.osman = textstat.osman(text_data)



def getRedabilityCSV(course_id):
    
    name_video = f"courses/{course_id}/videos.json"
    name_text = f"courses/{course_id}/texts.json"
    name_quiz = f"courses/{course_id}/quizes.json"

    with open(name_video, "r") as f:
        video_data = json.load(f)
    with open(name_text, "r") as f:
        text_data = json.load(f)
    with open(name_quiz, "r") as f:
        quiz_data = json.load(f)
    FIRST_ROW = ["index", "edx_id", "transcript", "flesch_reading_ease","flesch_kincaid_grade","smog_index","coleman_liau_index","automated_readability_index","dale_chall_readability_score","difficult_words","linsear_write_formula","gunning_fog","text_standard","fernandez_huerta","szigriszt_pazos","gutierrez_polini","crawford","gulpease_index","osman"]
    

    with open(f"courses/{course_id}/video.csv", 'w') as csv_f:
        writer = csv.writer(csv_f)
        writer.writerow(FIRST_ROW)
        for video_key in list(video_data.keys()):
            transcript = ". ".join(video_data[video_key]["transcript_en"])
            textRedability = TextRedability(transcript)
            edx_id = video_data[video_key]["id"]
            edx_id = edx_id.split("@")[-1]
            writer.writerow([video_key, edx_id, transcript,   textRedability.flesch_reading_ease, textRedability.flesch_kincaid_grade, textRedability.smog_index, textRedability.coleman_liau_index, textRedability.automated_readability_index, textRedability.dale_chall_readability_score, textRedability.difficult_words, textRedability.linsear_write_formula, textRedability.gunning_fog, textRedability.text_standard, textRedability.fernandez_huerta, textRedability.szigriszt_pazos, textRedability.gutierrez_polini, textRedability.crawford, textRedability.gulpease_index, textRedability.osman])
        
class ExitCode(Enum):
    WRONG_EMAIL_OR_PASSWORD = "Wrong email or password"